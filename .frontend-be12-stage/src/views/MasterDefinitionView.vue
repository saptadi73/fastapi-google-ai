<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import EtlShell from '@/components/EtlShell.vue'
import { call, copy, editRoles, reviewRoles, types, user } from '@/lib/etl'
import { blankDefinition, validateDefinition, type Candidate, type Master } from '@/lib/masters'
import { useTask } from '@/lib/tasks'
const route = useRoute(),
  router = useRouter()
const { busy, error, notice, run } = useTask()
const id = computed(() => String(route.params.id || ''))
const record = ref<Master | null>(null),
  draft = ref(blankDefinition()),
  code = ref(''),
  aliases = ref(''),
  comment = ref('')
const baseline = ref(''),
  candidateSnapshot = ref(''),
  candidates = ref<Candidate[] | null>(null),
  checked = ref<string[]>([]),
  reason = ref('')
const deactivate = ref(false)
const editor = computed(() => editRoles.includes(user.value?.role || ''))
const reviewer = computed(() => reviewRoles.includes(user.value?.role || ''))
function payload() {
  const definition = copy(draft.value)
  definition.aliases = aliases.value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
  if (definition.policy.source_conflict_policy !== 'AUTHORITATIVE_SOURCE')
    definition.policy.authoritative_source_sheet_id = null
  return { code: code.value, definition }
}
const serialized = computed(() => JSON.stringify(payload()))
const dirty = computed(() => !!baseline.value && serialized.value !== baseline.value)
const previewReady = computed(
  () =>
    candidates.value !== null &&
    candidateSnapshot.value === serialized.value &&
    candidates.value.every((c) => checked.value.includes(c.id)) &&
    (!candidates.value.length || !!reason.value.trim()),
)
const separate = computed(
  () =>
    !!record.value &&
    user.value?.id !== record.value.created_by &&
    user.value?.id !== record.value.submitted_by,
)
function accept(master: Master) {
  record.value = master
  code.value = master.code
  draft.value = copy(master.definition_json)
  aliases.value = master.definition_json.aliases.join('\n')
  baseline.value = JSON.stringify(payload())
  candidates.value = null
  checked.value = []
  candidateSnapshot.value = ''
  reason.value = ''
  deactivate.value = false
}
async function load() {
  const requested = id.value
  if (requested) {
    const master = await call<Master>('GET', `/master-definitions/${requested}`)
    if (requested === id.value) accept(master)
  }
}
async function preview() {
  validateDefinition(payload().definition)
  const snapshot = serialized.value
  const response = await call<{ candidates: Candidate[] }>(
    'POST',
    `/master-definitions/preview${id.value ? `?against=${id.value}` : ''}`,
    { ...payload(), reviewed_candidate_ids: [], duplicate_review_reason: '' },
  )
  if (snapshot !== serialized.value) return
  candidates.value = response.candidates
  checked.value = []
  reason.value = ''
  candidateSnapshot.value = snapshot
}
async function save() {
  if (!previewReady.value)
    throw new Error('Preview ulang dan tinjau seluruh kandidat sebelum menyimpan.')
  const body = {
    definition: payload().definition,
    reviewed_candidate_ids: checked.value,
    duplicate_review_reason: reason.value,
  }
  const result = record.value
    ? await call<Master>('PATCH', `/master-definitions/${record.value.id}`, {
        ...body,
        revision_no: record.value.revision_no,
      })
    : await call<Master>('POST', '/master-definitions', { ...body, code: code.value })
  accept(result)
  notice.value = 'Draft master tersimpan. Ajukan review sebelum approval.'
  if (!id.value) await router.replace(`/masters/${result.id}`)
}
async function action(name: string) {
  if (!record.value || dirty.value)
    throw new Error('Simpan atau muat ulang perubahan sebelum melanjutkan.')
  accept(
    await call<Master>('POST', `/master-definitions/${record.value.id}/${name}`, {
      revision_no: record.value.revision_no,
      comment: comment.value,
    }),
  )
  notice.value = `Keputusan tersimpan: ${record.value?.status}.`
}
watch(
  serialized,
  () => {
    candidates.value = null
    checked.value = []
    candidateSnapshot.value = ''
    reason.value = ''
  },
  { flush: 'sync' },
)
watch(
  [id, user],
  (_, previous) => {
    if (previous?.[1] === user.value && id.value && record.value?.id === id.value) return
    record.value = null
    code.value = ''
    draft.value = blankDefinition()
    aliases.value = ''
    comment.value = ''
    baseline.value = JSON.stringify(payload())
    candidates.value = null
    checked.value = []
    if (id.value && [...editRoles, ...reviewRoles].includes(user.value?.role || '')) void run(load)
  },
  { immediate: true },
)
async function reload() {
  if (!dirty.value || window.confirm('Buang perubahan definisi dan muat ulang?')) await load()
}
function canLeave() {
  return (
    !dirty.value || window.confirm('Perubahan definisi belum disimpan. Tinggalkan halaman ini?')
  )
}
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate(canLeave)
function beforeUnload(event: BeforeUnloadEvent) {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>
<template>
  <EtlShell
    ><RouterLink to="/masters">← Registry master</RouterLink>
    <RouterLink
      v-if="record?.is_active && record.approved_version > 0"
      class="button"
      :to="`/masters/${record.id}/storage`"
      >Storage &amp; record</RouterLink
    >
    <h1>{{ record ? 'Review definisi master' : 'Definisi master baru' }}</h1>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success" role="status">{{ notice }}</p>
    <p v-if="busy" role="status">Memproses…</p>
    <p v-if="record">
      {{ record.status }} · revisi {{ record.revision_no }} · versi approved
      {{ record.approved_version }}
    </p>
    <p v-if="dirty" class="notice">Perubahan belum disimpan.</p>
    <form class="panel" @submit.prevent="run(preview)">
      <fieldset :disabled="busy || !editor || (!!id && !record)">
        <h2>Identitas &amp; schema</h2>
        <div class="grid">
          <label
            >Kode master<input
              v-model="code"
              required
              pattern="[a-z][a-z0-9_]*"
              maxlength="63"
              :disabled="!!record" /></label
          ><label>Nama master<input v-model="draft.name" required maxlength="200" /></label
          ><label>Alias (satu per baris)<textarea v-model="aliases" /></label>
        </div>
        <label>Deskripsi master<textarea v-model="draft.description" maxlength="2000" /></label>
        <div v-for="(field, index) in draft.fields" :key="index" class="card-row">
          <div class="grid">
            <label
              >Nama field<input
                v-model="field.name"
                required
                pattern="[a-z][a-z0-9_]*"
                maxlength="63" /></label
            ><label
              >Tipe field<select v-model="field.type">
                <option v-for="type in types" :key="type">{{ type }}</option>
              </select></label
            ><label
              >Sensitivitas<select v-model="field.pii_classification">
                <option v-for="pii in ['NONE', 'LOW', 'MEDIUM', 'HIGH']" :key="pii">
                  {{ pii }}
                </option>
              </select></label
            >
          </div>
          <div class="toolbar">
            <label class="check"
              ><input v-model="field.nullable" type="checkbox" />Boleh kosong</label
            ><button
              type="button"
              :disabled="draft.fields.length === 1"
              @click="draft.fields.splice(index, 1)"
            >
              Hapus field
            </button>
          </div>
        </div>
        <button
          type="button"
          :disabled="draft.fields.length >= 100"
          @click="
            draft.fields.push({
              name: '',
              type: 'text',
              nullable: true,
              pii_classification: 'NONE',
            })
          "
        >
          Tambah field
        </button>
        <h3>Business key (maksimal 10)</h3>
        <label v-for="field in draft.fields.filter((f) => f.name)" :key="field.name" class="check"
          ><input
            v-model="draft.business_key"
            type="checkbox"
            :value="field.name"
            :disabled="
              field.nullable ||
              (draft.business_key.length >= 10 && !draft.business_key.includes(field.name))
            "
          />{{ field.name }}</label
        ><label
          >Field label<select v-model="draft.label_field" required>
            <option value="" disabled>Pilih label</option>
            <option v-for="field in draft.fields" :key="field.name" :value="field.name">
              {{ field.name }}
            </option>
          </select></label
        >
        <h2>Policy master</h2>
        <div class="grid">
          <label
            >Kode baru<select v-model="draft.policy.new_record_policy" required>
              <option value="PROPOSE_INSERT">
                PROPOSE_INSERT — usulkan insert dengan approval
              </option>
              <option value="UPDATE_ONLY">UPDATE_ONLY — hanya kode yang sudah ada</option>
            </select></label
          ><label
            >Konflik sumber<select v-model="draft.policy.source_conflict_policy" required>
              <option value="REQUIRE_REVIEW">REQUIRE_REVIEW</option>
              <option value="AUTHORITATIVE_SOURCE">AUTHORITATIVE_SOURCE</option>
            </select></label
          ><label v-if="draft.policy.source_conflict_policy === 'AUTHORITATIVE_SOURCE'"
            >UUID tab MASTER otoritatif<input
              v-model="draft.policy.authoritative_source_sheet_id"
              required
          /></label>
        </div>
        <p class="muted">
          Record hilang: KEEP · penonaktifan: EXPLICIT_REVIEW · perubahan key: EXPLICIT_MIGRATION ·
          referensi: RESTRICT. Otoritas tidak melewati review atau approval.
        </p>
        <label class="check"
          ><input
            type="checkbox"
            :checked="!!draft.policy.effective_dating"
            @change="
              draft.policy.effective_dating = ($event.target as HTMLInputElement).checked
                ? {
                    valid_from_column: '',
                    valid_to_column: '',
                    interval: 'START_INCLUSIVE_END_EXCLUSIVE',
                    overlap_policy: 'REJECT',
                  }
                : null
            "
          />Gunakan masa berlaku</label
        >
        <div v-if="draft.policy.effective_dating" class="grid">
          <label
            >Field awal berlaku<select
              v-model="draft.policy.effective_dating.valid_from_column"
              required
            >
              <option value="" disabled>Pilih field</option>
              <option
                v-for="field in draft.fields.filter((f) =>
                  ['date', 'timestamp', 'timestamptz'].includes(f.type),
                )"
                :key="field.name"
              >
                {{ field.name }}
              </option>
            </select></label
          ><label
            >Field akhir berlaku<select
              v-model="draft.policy.effective_dating.valid_to_column"
              required
            >
              <option value="" disabled>Pilih field</option>
              <option
                v-for="field in draft.fields.filter((f) =>
                  ['date', 'timestamp', 'timestamptz'].includes(f.type),
                )"
                :key="field.name"
              >
                {{ field.name }}
              </option>
            </select></label
          >
          <p>Awal inklusif, akhir eksklusif; overlap ditolak oleh runtime tahap berikutnya.</p>
        </div>
        <button>Preview kandidat master</button>
      </fieldset>
    </form>
    <section v-if="candidates !== null" class="panel">
      <h2>Review kandidat serupa</h2>
      <p v-if="!candidates.length">
        Tidak ditemukan kandidat serupa. Preview belum menyimpan master.
      </p>
      <div v-for="candidate in candidates" :key="candidate.id" class="card-row">
        <p>
          {{ candidate.name }} · {{ candidate.code }} · {{ candidate.status }} · skor
          {{ candidate.score }}
        </p>
        <p>{{ candidate.reason }}</p>
        <RouterLink class="button" :to="`/masters/${candidate.id}`"
          >Periksa master yang sudah ada</RouterLink
        ><label class="check"
          ><input v-model="checked" type="checkbox" :value="candidate.id" :disabled="busy" />Sudah
          diperiksa; definisi ini berbeda</label
        >
      </div>
      <label v-if="candidates.length"
        >Alasan definisi berbeda<textarea
          v-model="reason"
          required
          maxlength="2000"
          :disabled="busy"
        /></label
      ><button class="primary" :disabled="busy || !editor || !previewReady" @click="run(save)">
        Simpan draft master
      </button>
    </section>
    <section v-if="record" class="panel">
      <h2>Keputusan review</h2>
      <p class="muted">
        Approval menghasilkan versi baru dan dapat membuat binding versi lama stale. Editor/pengaju
        tidak menyetujui definisi sendiri.
      </p>
      <label
        >Catatan keputusan<textarea v-model="comment" maxlength="2000" :disabled="busy" />
      </label>
      <div class="toolbar">
        <button :disabled="busy" @click="run(reload)">Muat ulang definisi</button
        ><button
          v-if="editor && ['DRAFT', 'REJECTED'].includes(record.status)"
          :disabled="busy || dirty"
          @click="run(() => action('submit-review'))"
        >
          Ajukan review master</button
        ><template v-if="reviewer && record.status === 'NEEDS_REVIEW'"
          ><button
            class="primary"
            :disabled="busy || dirty || !separate"
            @click="run(() => action('approve'))"
          >
            Setujui master</button
          ><button :disabled="busy || dirty" @click="run(() => action('reject'))">
            Tolak master
          </button></template
        >
      </div>
      <template v-if="reviewer && record.is_active"
        ><label class="check"
          ><input v-model="deactivate" type="checkbox" :disabled="busy" />Saya memahami penonaktifan
          membuat binding tidak ready.</label
        ><button
          :disabled="busy || dirty || !deactivate || !comment.trim()"
          @click="run(() => action('deactivate'))"
        >
          Nonaktifkan master
        </button></template
      >
    </section>
    <details v-if="record?.approved_definition_json" class="panel">
      <summary>Snapshot approved v{{ record.approved_version }}</summary>
      <p class="muted">Binding menggunakan snapshot ini, bukan working draft di atas.</p>
      <pre>{{ JSON.stringify(record.approved_definition_json, null, 2) }}</pre>
    </details>
  </EtlShell>
</template>
