<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import EtlShell from '@/components/EtlShell.vue'
import DataTable from '@/components/DataTable.vue'
import { call, editRoles, reviewRoles, user } from '@/lib/etl'
import {
  answerImportReviewQuestion,
  applyImportReview,
  approveImportReview,
  type Finding,
  type ImportQuestion,
  type ImportQuestionAction,
  type ImportQuestionActionResponse,
  type ImportQuestionCategory,
  type ImportQuestionDecision,
  type ImportQuestionResolve,
  type ImportReviewPreview,
  listImportReviewQuestions,
  previewImportReview,
  resolveImportReference,
  type ImportReferenceResolveResult,
  resolveImportReviewMasterProposal,
  type ImportReview,
} from '@/lib/importReviews'
import { useTask } from '@/lib/tasks'
const route = useRoute(),
  id = computed(() => String(route.params.id)),
  { busy, error, notice, run } = useTask()
const review = ref<ImportReview | null>(null),
  findings = ref<Finding[]>([]),
  findingsMore = ref(false),
  findingOffset = ref(0),
  questions = ref<ImportQuestion[]>([]),
  questionsMore = ref(false),
  questionOffset = ref(0),
  questionStatus = ref(''),
  questionCategory = ref(''),
  preview = ref<ImportReviewPreview | null>(null),
  appliedRows = ref<number | null>(null),
  referenceMasterId = ref(''),
  referenceValue = ref(''),
  referenceQuestionId = ref(''),
  referenceResult = ref<ImportReferenceResolveResult | null>(null)
interface QuestionAnswerDraft {
  action: ImportQuestionAction | ''
  correctedValue: string
  reason: string
  selectedCandidateId: string
  masterProposalText: string
  proposedMasterDefinitionId: string
}
const comment = ref(''),
  questionDrafts = ref<Record<string, QuestionAnswerDraft>>({})
const findingRows = computed(() => findings.value as Record<string, unknown>[])
const previewRows = computed(() => (preview.value?.changes || []) as Record<string, unknown>[])
const referenceRows = computed(() => {
  if (!referenceResult.value) return []
  if (referenceResult.value.record) return [referenceResult.value.record]
  return referenceResult.value.candidates || []
})
const aiMetadata = computed(() => review.value?.checkpoint.ai_metadata || [])
const referenceTargets = computed(() =>
  questions.value.filter(
    (question) => question.staging_row_id && question.target_column && question.status === 'OPEN',
  ),
)
const questionItems = computed(() =>
  questions.value.map((question) => {
    initDraft(question)
    return { question, draft: questionDrafts.value[question.id] as QuestionAnswerDraft }
  }),
)
const canEdit = computed(() => editRoles.includes(user.value?.role || ''))
const canReview = computed(() => reviewRoles.includes(user.value?.role || ''))
const canPreview = computed(
  () =>
    canEdit.value &&
    !!review.value &&
    ['READY_FOR_APPROVAL', 'APPROVED'].includes(review.value.status) &&
    !(review.value.checkpoint.blocking_codes || []).length &&
    review.value.dependencies_current !== false,
)
const canApprove = computed(
  () =>
    canReview.value &&
    !!review.value &&
    !!preview.value?.preview_token &&
    preview.value.can_approve &&
    review.value.status === 'READY_FOR_APPROVAL',
)
const canApply = computed(
  () =>
    canEdit.value &&
    !!review.value &&
    !!preview.value?.preview_token &&
    review.value.status === 'APPROVED',
)
const questionStatusItems: Array<'' | ImportQuestion['status']> = [
  '',
  'OPEN',
  'ANSWERED',
  'PENDING_APPROVAL',
  'CANCELLED',
]
const questionCategoryItems: Array<'' | ImportQuestionCategory> = [
  '',
  'DATA_QUALITY',
  'DUPLICATE_KEY',
  'DATA_QUALITY_WARNING',
  'CONFIGURATION',
  'AI_REVIEW',
]
const terminal = ['NEEDS_INPUT', 'FAILED', 'STALE_REVIEW', 'CANCELLED', 'SUCCEEDED', 'APPROVED']
let timer: ReturnType<typeof setTimeout> | undefined
let generation = 0
function stop() {
  ++generation
  if (timer) clearTimeout(timer)
}
function initDraft(question: ImportQuestion) {
  const current = questionDrafts.value[question.id]
  const defaultAction = question.allowed_actions[0] ?? ''
  if (!current) {
    questionDrafts.value[question.id] = {
      action: defaultAction,
      correctedValue: '',
      reason: '',
      selectedCandidateId: '',
      masterProposalText: '',
      proposedMasterDefinitionId: question.proposed_master_definition_id || '',
    }
    return
  }
  if (current.action && !question.allowed_actions.includes(current.action)) {
    current.action = defaultAction
  }
  if (!current.proposedMasterDefinitionId) {
    current.proposedMasterDefinitionId = question.proposed_master_definition_id || ''
  }
}
async function loadFindings(next = 0) {
  const result = await call<{ items: Finding[]; has_more: boolean }>(
    'GET',
    `/import-reviews/${id.value}/findings?offset=${next}&limit=50`,
  )
  findings.value = result.items
  findingsMore.value = result.has_more
  findingOffset.value = next
}
async function loadQuestions(next = 0) {
  const result = await listImportReviewQuestions(
    id.value,
    questionStatus.value,
    questionCategory.value,
    next,
    50,
  )
  questions.value = result.items
  questionsMore.value = result.has_more
  questionOffset.value = next
  for (const question of result.items) initDraft(question)
}
function normalizeCorrectionValue(raw: string) {
  const trimmed = raw.trim()
  if (!trimmed) return trimmed
  try {
    return JSON.parse(trimmed)
  } catch {
    return trimmed
  }
}
function requiresReason(action: ImportQuestionAction | '') {
  return action === 'CORRECT_SOURCE' || action === 'PROPOSE_MASTER'
}
function candidateLabel(candidate: Record<string, unknown>) {
  return typeof candidate.label === 'string' && candidate.label
    ? candidate.label
    : String(candidate.id)
}
function buildAnswerPayload(question: ImportQuestion): ImportQuestionDecision {
  const draft = questionDrafts.value[question.id]
  if (!draft || !draft.action) throw new Error('Pilih tindakan dahulu.')
  const payload: ImportQuestionDecision = {
    revision_no: question.revision_no,
    action: draft.action,
  }
  if (draft.action === 'APPLY_CORRECTION') {
    if (!draft.correctedValue.trim()) throw new Error('Nilai koreksi wajib diisi.')
    payload.corrected_value = normalizeCorrectionValue(draft.correctedValue)
  } else if (draft.action === 'PROPOSE_MASTER') {
    if (!draft.reason.trim()) throw new Error('Alasan usulan master wajib diisi.')
    payload.reason = draft.reason.trim()
    if (!draft.masterProposalText.trim()) throw new Error('Payload master proposal wajib diisi.')
    try {
      payload.master_proposal = JSON.parse(draft.masterProposalText.trim())
    } catch {
      throw new Error('Master proposal harus JSON yang valid.')
    }
  } else if (draft.action === 'CORRECT_SOURCE') {
    if (!draft.reason.trim()) throw new Error('Alasan koreksi sumber wajib diisi.')
    payload.reason = draft.reason.trim()
  } else if (draft.action === 'SELECT_RECORD') {
    if (!draft.selectedCandidateId.trim()) throw new Error('Pilih kandidat yang sesuai.')
    payload.selected_candidate_id = draft.selectedCandidateId.trim()
  } else if (draft.action === 'KEEP_ORIGINAL') {
    if (question.mandatory) throw new Error('KEEP_ORIGINAL tidak tersedia untuk pertanyaan wajib.')
  }
  if (requiresReason(draft.action)) payload.reason = draft.reason.trim()
  return payload
}
function applyQuestionResponse(response: ImportQuestionActionResponse) {
  review.value = response.review
  preview.value = null
  appliedRows.value = null
  const updated = response.question
  if (updated) {
    const index = questions.value.findIndex((item) => item.id === updated.id)
    if (index >= 0) questions.value[index] = updated
  }
}
async function answerQuestion(question: ImportQuestion) {
  const response = await answerImportReviewQuestion(
    id.value,
    question.id,
    buildAnswerPayload(question),
  )
  if (response.stale) {
    notice.value = 'Batch menjadi stale karena dependency berubah. Muat ulang batch.'
    await load()
    return
  }
  applyQuestionResponse(response)
  await loadFindings()
  await loadQuestions(questionOffset.value)
}
async function resolveProposal(question: ImportQuestion) {
  const draft = questionDrafts.value[question.id]
  const payload: ImportQuestionResolve = {
    revision_no: question.revision_no,
    master_definition_id: (draft?.proposedMasterDefinitionId || '').trim(),
  }
  if (!payload.master_definition_id) throw new Error('Pilih master definition yang disetujui.')
  const response = await resolveImportReviewMasterProposal(id.value, question.id, payload)
  if (response.stale) {
    notice.value = 'Batch menjadi stale setelah status proposal. Muat ulang batch.'
    await load()
    return
  }
  applyQuestionResponse(response)
  await loadFindings()
  await loadQuestions(questionOffset.value)
}
async function load() {
  stop()
  const epoch = generation
  const result = await call<ImportReview>('GET', `/import-reviews/${id.value}`)
  if (epoch !== generation) return
  review.value = result
  preview.value = null
  appliedRows.value = null
  await Promise.all([loadFindings(), loadQuestions()])
  if (epoch === generation && !terminal.includes(result.status))
    timer = setTimeout(() => void poll(epoch), 3000)
}
async function poll(epoch: number) {
  if (epoch !== generation) return
  const result = await call<ImportReview>('GET', `/import-reviews/${id.value}`)
  if (epoch !== generation) return
  review.value = result
  if (!terminal.includes(result.status)) {
    timer = setTimeout(() => void poll(epoch), 3000)
    return
  }
  await Promise.all([loadFindings(), loadQuestions()])
}
async function action(kind: 'cancel' | 'revalidate' | 'resume') {
  if (!review.value) return
  const result = await call<ImportReview>('POST', `/import-reviews/${id.value}/${kind}`, {
    revision_no: review.value.revision_no,
    comment: comment.value.trim(),
  })
  review.value = result
  preview.value = null
  appliedRows.value = null
  notice.value = `Aksi ${kind} diterima. Periksa status batch terbaru.`
  await Promise.all([loadFindings(), loadQuestions()])
}
async function previewBatch() {
  if (!review.value) return
  preview.value = await previewImportReview(id.value, review.value.revision_no)
  review.value = preview.value.review
  appliedRows.value = null
  notice.value = 'Preview batch siap ditinjau.'
}
async function approveBatch() {
  if (!review.value || !preview.value) return
  review.value = await approveImportReview(id.value, review.value.revision_no, comment.value)
  notice.value = 'Preview batch disetujui. Editor dapat menjalankan apply dengan token yang sama.'
}
async function applyBatch() {
  if (!review.value || !preview.value) return
  const result = await applyImportReview(
    id.value,
    review.value.revision_no,
    preview.value.preview_token,
  )
  review.value = result.review
  appliedRows.value = result.rows_applied
  notice.value = `Apply selesai. ${result.rows_applied} baris diproses.`
  await Promise.all([loadFindings(), loadQuestions()])
}
async function resolveReference() {
  if (!review.value) return
  const target = referenceTargets.value.find(
    (question) => question.id === referenceQuestionId.value,
  )
  referenceResult.value = await resolveImportReference(
    id.value,
    review.value.revision_no,
    referenceMasterId.value.trim(),
    referenceValue.value.trim(),
    target?.staging_row_id || undefined,
    target?.target_column || undefined,
  )
  if (referenceResult.value.staging_updated) {
    preview.value = null
    appliedRows.value = null
    notice.value = 'Reference tepat ditemukan dan nilai staging telah diisi. Buat preview baru.'
    await Promise.all([loadFindings(), loadQuestions(questionOffset.value)])
  }
}
watch(
  [id, user],
  () => {
    review.value = null
    findings.value = []
    questions.value = []
    questionDrafts.value = {}
    preview.value = null
    appliedRows.value = null
    referenceQuestionId.value = ''
    referenceResult.value = null
    if (user.value) void run(load)
  },
  { immediate: true },
)
onBeforeUnmount(stop)
</script>
<template>
  <EtlShell
    ><RouterLink to="/import-reviews">â† Daftar batch</RouterLink>
    <h1>Detail batch import</h1>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <template v-if="review"
      ><section class="panel">
        <h2>{{ review.status }} Â· {{ review.dataset_kind }}</h2>
        <p>
          {{ review.id }} Â· revisi {{ review.revision_no }} Â· generasi {{ review.generation }}
        </p>
        <p>
          Snapshot {{ review.snapshot_hash }} Â· dependency
          {{ review.dependencies_current === false ? 'berubah' : 'terkini' }}
        </p>
        <p v-if="review.configuration_id">
          Konfigurasi {{ review.configuration_id }} Â· revisi {{ review.configuration_revision }}
        </p>
        <p v-if="review.master_id">
          Master {{ review.master_id }} Â· versi {{ review.master_version }}
        </p>
        <p v-if="review.checkpoint.blocking_codes?.length" class="error">
          Blocker: {{ review.checkpoint.blocking_codes.join(', ') }}
        </p>
        <p>
          Baris valid {{ review.checkpoint.rows_valid ?? 'â€”' }} Â· invalid
          {{ review.checkpoint.rows_invalid ?? 'â€”' }} Â· warning
          {{ review.checkpoint.warning_count ?? 0 }} Â· AI
          {{ review.checkpoint.ai_coverage || 'â€”' }}
        </p>
        <section v-if="review.checkpoint.ai_coverage" class="card-row">
          <h3>Evidence review AI</h3>
          <p>
            Coverage {{ review.checkpoint.ai_coverage }} ·
            {{ review.checkpoint.ai_reviewed_rows?.length || 0 }} baris direview
          </p>
          <p class="muted">
            Field disamarkan: {{ review.checkpoint.ai_masked_fields?.join(', ') || 'tidak ada' }}
          </p>
          <details v-if="aiMetadata.length">
            <summary>Metadata model dan prompt</summary>
            <pre>{{ JSON.stringify(aiMetadata, null, 2) }}</pre>
          </details>
        </section>
        <p v-if="review.status === 'SUCCEEDED'" class="notice">
          Batch sudah selesai diaplikasikan ke target trusted.
          {{ appliedRows === null ? '' : `${appliedRows} baris diproses.` }}
        </p>
        <label v-if="canEdit"
          >Catatan aksi<textarea v-model="comment" maxlength="2000" :disabled="busy" />
        </label>
        <div v-if="canEdit" class="toolbar">
          <button
            :disabled="
              busy || ['CANCELLED', 'SUCCEEDED', 'APPLYING', 'APPROVED'].includes(review.status)
            "
            @click="run(() => action('cancel'))"
          >
            Batalkan batch</button
          ><button
            :disabled="busy || !['FAILED', 'STALE_REVIEW'].includes(review.status)"
            @click="run(() => action('revalidate'))"
          >
            Revalidate</button
          ><button
            :disabled="busy || review.status !== 'NEEDS_INPUT'"
            @click="run(() => action('resume'))"
          >
            Resume
          </button>
        </div>
      </section>
      <section class="panel">
        <h2>Preview dan apply</h2>
        <p class="muted">
          Preview mengikat snapshot dan revision batch. Jika batch berubah, buat preview baru.
        </p>
        <div class="toolbar">
          <button class="primary" :disabled="busy || !canPreview" @click="run(previewBatch)">
            Buat preview</button
          ><button :disabled="busy || !canApprove" @click="run(approveBatch)">
            Approve preview</button
          ><button :disabled="busy || !canApply" @click="run(applyBatch)">Apply batch</button>
        </div>
        <template v-if="preview">
          <p>
            Target {{ preview.target }} · hash {{ preview.preview_hash }} ·
            {{ preview.can_approve ? 'siap approval' : 'belum siap approval' }}
          </p>
          <pre>{{ JSON.stringify(preview.summary, null, 2) }}</pre>
          <DataTable :rows="previewRows" />
        </template>
        <form class="toolbar" @submit.prevent="run(resolveReference)">
          <label
            >Master ID<input
              v-model="referenceMasterId"
              required
              placeholder="UUID master definition"
              :disabled="busy"
          /></label>
          <label
            >Value<input
              v-model="referenceValue"
              required
              maxlength="500"
              placeholder="Nilai business key"
              :disabled="busy"
          /></label>
          <label
            >Isi staging (opsional)<select v-model="referenceQuestionId" :disabled="busy">
              <option value="">Hanya cari reference</option>
              <option v-for="question in referenceTargets" :key="question.id" :value="question.id">
                Baris {{ question.source_row || '?' }} · {{ question.target_column }}
              </option>
            </select></label
          >
          <button :disabled="busy || !review">Resolve reference</button>
        </form>
        <template v-if="referenceResult">
          <p>Reference {{ referenceResult.status }} · master {{ referenceResult.master_id }}</p>
          <p v-if="referenceResult.staging_updated" class="success">
            Nilai staging diperbarui dari record master yang tepat.
          </p>
          <DataTable :rows="referenceRows" />
        </template>
      </section>
      <section class="panel">
        <h2>Temuan ({{ review.finding_count }})</h2>
        <p class="muted">Nilai sel mentah tidak ditampilkan.</p>
        <DataTable :rows="findingRows" />
        <div class="toolbar">
          <button
            :disabled="busy || findingOffset === 0"
            @click="run(() => loadFindings(Math.max(0, findingOffset - 50)))"
          >
            Sebelumnya</button
          ><button
            :disabled="busy || !findingsMore"
            @click="run(() => loadFindings(findingOffset + 50))"
          >
            Berikutnya
          </button>
        </div>
      </section>
      <section class="panel">
        <h2>Pertanyaan batch</h2>
        <div class="toolbar">
          <select v-model="questionStatus" @change="run(() => loadQuestions(0))">
            <option v-for="status in questionStatusItems" :key="status">
              {{ status || 'Semua status' }}
            </option></select
          ><select v-model="questionCategory" @change="run(() => loadQuestions(0))">
            <option v-for="category in questionCategoryItems" :key="category">
              {{ category || 'Semua kategori' }}
            </option></select
          ><button :disabled="busy" @click="run(() => loadQuestions(0))">Muat ulang</button>
        </div>
        <p v-if="!questions.length" class="muted">Belum ada pertanyaan untuk batch ini.</p>
        <article v-for="item in questionItems" :key="item.question.id" class="card-row">
          <h3>
            {{ item.question.category }} � {{ item.question.status }} � baris
            {{ item.question.source_row || '�' }}
          </h3>
          <p>{{ item.question.prompt }}</p>
          <p>
            Kolom {{ item.question.source_column || '�' }} =>
            {{ item.question.target_column || '�' }} �
            {{ item.question.mandatory ? 'Wajib' : 'Opsional' }}
            {{
              item.question.decisions.length
                ? ` � keputusan: ${item.question.decisions.length}`
                : ''
            }}
          </p>
          <template v-if="item.question.status === 'OPEN' && canEdit">
            <label
              >Tindakan<select v-model="item.draft.action" :disabled="busy">
                <option v-for="action in item.question.allowed_actions" :key="action">
                  {{ action }}
                </option>
              </select></label
            >
            <label v-if="item.draft.action === 'APPLY_CORRECTION'"
              >Nilai koreksi<input
                v-model="item.draft.correctedValue"
                placeholder='321 atau "abc"'
                :disabled="busy"
              />
            </label>
            <label v-if="item.draft.action === 'SELECT_RECORD'"
              >Pilih kandidat<select v-model="item.draft.selectedCandidateId" :disabled="busy">
                <option value="">Pilih kandidat</option>
                <option
                  v-for="candidate in item.question.candidates"
                  :key="candidate.id"
                  :value="candidate.id"
                >
                  {{ candidateLabel(candidate) }}
                </option>
              </select></label
            >
            <label v-if="requiresReason(item.draft.action)"
              >Alasan<textarea v-model="item.draft.reason" maxlength="2000" :disabled="busy" />
            </label>
            <label v-if="item.draft.action === 'PROPOSE_MASTER'"
              >Master proposal (JSON)<textarea
                v-model="item.draft.masterProposalText"
                maxlength="4000"
                placeholder='{"code":"kode_master","name":"Nama"}'
                :disabled="busy"
              />
            </label>
            <div class="toolbar">
              <button
                class="primary"
                :disabled="busy"
                @click="run(() => answerQuestion(item.question))"
              >
                Simpan jawaban
              </button>
            </div>
          </template>
          <template v-else-if="item.question.status === 'PENDING_APPROVAL' && canReview">
            <label
              >Master definition approved (ID)<input
                v-model="item.draft.proposedMasterDefinitionId"
                placeholder="UUID master definition"
                :disabled="busy"
            /></label>
            <button
              class="primary"
              :disabled="busy"
              @click="run(() => resolveProposal(item.question))"
            >
              Selesaikan proposal master
            </button>
          </template>
          <div v-else>
            <pre>{{ JSON.stringify(item.question.decisions, null, 2) }}</pre>
          </div>
        </article>
        <div class="toolbar">
          <button
            :disabled="busy || questionOffset === 0"
            @click="run(() => loadQuestions(Math.max(0, questionOffset - 50)))"
          >
            Sebelumnya</button
          ><button
            :disabled="busy || !questionsMore"
            @click="run(() => loadQuestions(questionOffset + 50))"
          >
            Berikutnya
          </button>
        </div>
      </section></template
    >
    <p v-else-if="busy" role="status">Memuat batchâ€¦</p></EtlShell
  >
</template>
