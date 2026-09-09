<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import EtlShell from '@/components/EtlShell.vue'
import ConfigurationHistory from '@/components/ConfigurationHistory.vue'
import SheetClassification from '@/components/SheetClassification.vue'
import Card from '@/components/ui/Card.vue'
import Modal from '@/components/ui/Modal.vue'
import Spinner from '@/components/ui/Spinner.vue'
import CardSkeleton from '@/components/ui/CardSkeleton.vue'
import {
  CircleCheck,
  CircleX,
  Copy,
  Download,
  GitBranch,
  RefreshCw,
  Rocket,
  Save,
  Upload,
} from '@lucide/vue'
import { classificationEvidenceMatches } from '@/lib/classification'
import { downloadFile, getApiErrorMessage } from '@/lib/api'
import {
  call,
  copy,
  currencies,
  dqFormats,
  dqSeverities,
  editRoles,
  numberLocales,
  qualityRules,
  reviewRoles,
  roles,
  roundings,
  sections,
  sectionLabels,
  transforms,
  types,
  units,
  user,
  type Column,
  type ETL,
  type Quality,
  type Review,
  type Preview,
  type Config,
  type Job,
} from '@/lib/etl'
const route = useRoute(),
  router = useRouter()
const details = ref<Review | null>(null),
  draft = ref<ETL | null>(null),
  preview = ref<Preview | null>(null),
  parameterCatalog = ref<{
    schema_version: string
    parameters: Array<Record<string, unknown>>
    operations: Array<Record<string, unknown>>
    capabilities: Record<string, unknown>
  } | null>(null)
const error = ref(''),
  notice = ref(''),
  busy = ref(false),
  step = ref(0),
  comment = ref('')
const answers = ref<Record<string, string>>({}),
  resolved = ref<string[]>([])
const checkedColumns = ref<string[]>([]),
  checkedSections = ref<string[]>([]),
  job = ref<Job | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined
let generation = 0
let pollDeadline = 0
const configId = computed(() => String(route.params.id))
const base = computed(() => `/configurations/${configId.value}`)
const record = computed(() => details.value?.configuration)
const isDraft = computed(
  () => !!record.value && ['AI_DRAFT', 'NEEDS_REVIEW'].includes(record.value.status),
)
const editor = computed(() => !!user.value && editRoles.includes(user.value.role))
const canEdit = computed(() => editor.value && isDraft.value)
const reviewer = computed(() => !!user.value && reviewRoles.includes(user.value.role))
const dirty = computed(
  () =>
    !!draft.value &&
    (JSON.stringify(draft.value) !== JSON.stringify(record.value?.configuration_json) ||
      resolved.value.length > 0 ||
      Object.values(answers.value).some(Boolean)),
)
const submitted = computed(
  () =>
    record.value?.review_state?.submitted_revision === record.value?.revision_no &&
    evidenceReady.value,
)
const evidenceReady = computed(
  () =>
    !!record.value && classificationEvidenceMatches(record.value, details.value?.classification),
)
const ready = computed(
  () =>
    !dirty.value &&
    details.value?.validation.ready_for_review === true &&
    !!details.value.validation.snapshot_hash &&
    checkedColumns.value.length === draft.value?.columns.length &&
    checkedSections.value.length === sections.length,
)
const publicColumns = computed(
  () => draft.value?.columns.filter((c) => ['NONE', 'LOW'].includes(c.pii_classification)) || [],
)
const unusedHeaders = computed(
  () =>
    details.value?.profile?.columns.filter(
      (c) => !draft.value?.columns.some((x) => x.source_column === c.source_column),
    ) || [],
)
const selectedHeader = ref('')
const rollbackAcknowledged = ref(false)
const decisionModal = ref<'approve' | 'reject' | null>(null)
async function run(action: () => Promise<void>) {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await action()
  } catch (e) {
    error.value = getApiErrorMessage(e)
  } finally {
    busy.value = false
  }
}
async function load() {
  const epoch = generation
  const [result, catalog] = await Promise.all([
    call<Review>('GET', `${base.value}/review`),
    call<typeof parameterCatalog.value>('GET', '/configurations/parameter-catalog'),
  ])
  if (epoch !== generation) return
  details.value = result
  parameterCatalog.value = catalog
  draft.value = copy(result.configuration.configuration_json)
  answers.value = {}
  resolved.value = []
  preview.value = null
  checkedColumns.value = []
  checkedSections.value = []
}
function payload() {
  if (!draft.value || !record.value) throw new Error('Draft belum tersedia.')
  const configuration = copy(draft.value),
    question_answers: Record<string, string> = {}
  for (const q of resolved.value) {
    const answer = answers.value[q]?.trim()
    if (!answer) throw new Error(`Isi jawaban: ${q}`)
    question_answers[q] = answer
  }
  if (
    Object.keys(answers.value).some((q) => answers.value[q]?.trim() && !resolved.value.includes(q))
  )
    throw new Error('Tandai pertanyaan yang sudah dijawab sebagai selesai sebelum menyimpan.')
  configuration.unresolved_questions = configuration.unresolved_questions.filter(
    (q) => !resolved.value.includes(q),
  )
  return { revision_no: record.value.revision_no, configuration, question_answers }
}
async function save() {
  await call('PATCH', base.value, payload())
  await load()
  notice.value =
    'Draft tersimpan. Periksa hasil validasi dan centang bagian yang sudah diverifikasi.'
}
async function validate() {
  if (dirty.value) throw new Error('Simpan perubahan sebelum dry-run.')
  await load()
  notice.value =
    'Validasi diperbarui terhadap snapshot profiling terakhir. Periksa kembali checklist.'
}
async function submit() {
  if (!ready.value || !record.value) throw new Error('Lengkapi pemeriksaan semua bagian dan kolom.')
  await call('POST', `${base.value}/submit-review`, {
    revision_no: record.value.revision_no,
    snapshot_hash: details.value?.validation.snapshot_hash,
    reviewed_columns: checkedColumns.value,
    reviewed_sections: checkedSections.value,
  })
  await load()
  notice.value =
    'Review diajukan. Akun technical approver yang berbeda dapat memeriksa dan menyetujuinya.'
}
async function decision(action: 'approve' | 'reject') {
  if (dirty.value) throw new Error('Simpan atau muat ulang perubahan terlebih dahulu.')
  await call('POST', `${base.value}/${action}`, {
    revision_no: record.value?.revision_no,
    comment: comment.value,
  })
  await load()
  notice.value =
    action === 'approve'
      ? 'Disetujui. Jalankan deployment untuk mengaktifkan konfigurasi.'
      : 'Konfigurasi ditolak. Clone untuk membuat perbaikan.'
  decisionModal.value = null
}
async function clone() {
  const c = await call<Config>('POST', `${base.value}/clone`)
  await router.push(`/configurations/${c.id}/review`)
}
async function poll(id: string, epoch: number) {
  if (epoch !== generation || !user.value) return
  try {
    const result = await call<Job>('GET', `/jobs/${id}`)
    if (epoch !== generation) return
    job.value = result
    if (['QUEUED', 'RUNNING'].includes(result.status) && Date.now() < pollDeadline)
      timer = setTimeout(() => void poll(id, epoch), 2500)
    else if (['QUEUED', 'RUNNING'].includes(result.status))
      notice.value = 'Batas pemantauan tercapai. Buka monitor job untuk melanjutkan.'
    else if (dirty.value)
      notice.value = 'Job selesai. Simpan atau buang perubahan sebelum memuat hasil terbaru.'
    else await load()
  } catch (e) {
    error.value = getApiErrorMessage(e)
  }
}
async function queue(path: string) {
  const result = await call<{ job_id: string }>('POST', path)
  clearTimeout(timer)
  pollDeadline = Date.now() + 120_000
  await poll(result.job_id, generation)
}
async function syncReview() {
  if (!record.value) return
  const result = await call<{ reviews: unknown[] }>(
    'POST',
    `/sources/${record.value.source_id}/sync-review`,
  )
  notice.value = `Batch review dibuat untuk ${result.reviews.length} tab. Lanjutkan dari halaman batch import.`
  await router.push('/import-reviews')
}
async function download() {
  if (dirty.value) throw new Error('Simpan draft sebelum mengunduh Excel.')
  const a = await call<{ id: string; file_name: string }>('POST', `${base.value}/export`, {
    format: 'XLSX',
  })
  await downloadFile(`${base.value}/artifacts/${a.id}/download`, a.file_name)
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement,
    file = input.files?.[0]
  input.value = ''
  if (!file) return
  await run(async () => {
    preview.value = null
    if (dirty.value) throw new Error('Simpan atau muat ulang draft sebelum mengimpor Excel.')
    if (file.size > (details.value?.capabilities.max_workbook_bytes || 2_000_000))
      throw new Error('File maksimal 2 MB.')
    const encoded = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onerror = () => reject(new Error('File tidak dapat dibaca.'))
      reader.onload = () => resolve(String(reader.result).split(',')[1] || '')
      reader.readAsDataURL(file)
    })
    preview.value = await call<Preview>('POST', `${base.value}/workbook-preview`, {
      content_base64: encoded,
    })
  })
}
async function applyWorkbook() {
  if (
    !preview.value?.can_apply ||
    !preview.value.configuration ||
    !preview.value.preview_token ||
    dirty.value
  )
    throw new Error('Lakukan preview ulang sebelum menerapkan perubahan.')
  const p = preview.value
  await call('POST', `${base.value}/workbook-apply`, {
    revision_no: p.revision_no,
    configuration: p.configuration,
    question_answers: p.question_answers,
    preview_token: p.preview_token,
  })
  await load()
  notice.value =
    'Perubahan Excel disimpan sebagai draft. Verifikasi dan ajukan review untuk persetujuan.'
}
function addColumn() {
  if (!selectedHeader.value || !draft.value) return
  const name = selectedHeader.value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  draft.value.columns.push({
    source_column: selectedHeader.value,
    target_column: /^[a-z]/.test(name) ? name.slice(0, 63) : `col_${name}`.slice(0, 63),
    target_type: 'text',
    business_name: selectedHeader.value,
    nullable: true,
    is_primary_key: false,
    is_business_key: false,
    transformation_codes: [],
    pii_classification: 'NONE',
    confidence: 1,
    reason: 'Ditambahkan pengguna; periksa tipe dan sensitivitas data.',
    numeric_precision: null,
    numeric_scale: null,
    varchar_length: null,
    date_format: null,
    number_locale: null,
    source_timezone: null,
    unit_conversion: null,
    currency_conversion: null,
  })
  selectedHeader.value = ''
}
function addQuality() {
  draft.value?.data_quality_rules.push({
    column: draft.value.columns[0]?.target_column || '',
    rule: 'not_null',
    value: null,
    action_on_fail: 'REJECT_ROW',
    severity: 'ERROR',
    owner: null,
    threshold_percent: null,
    max_age_days: null,
    default_value: null,
  })
}
function qualityValue(q: Quality, event: Event) {
  const value = (event.target as HTMLInputElement).value
  q.value =
    q.rule === 'allowed_values'
      ? value.split('\n').filter(Boolean)
      : value === ''
        ? null
        : Number(value)
}
function defaultValueInput(q: Quality, event: Event) {
  const value = (event.target as HTMLInputElement).value
  if (value === '') {
    q.default_value = null
    return
  }
  try {
    const parsed: unknown = JSON.parse(value)
    q.default_value =
      typeof parsed === 'string' || typeof parsed === 'number' || typeof parsed === 'boolean'
        ? parsed
        : value
  } catch {
    q.default_value = value
  }
}
function defaultValueText(q: Quality) {
  return q.default_value === null || q.default_value === undefined
    ? ''
    : typeof q.default_value === 'string'
      ? q.default_value
      : JSON.stringify(q.default_value)
}
function setConversion(c: Column, kind: 'none' | 'unit' | 'currency') {
  c.unit_conversion =
    kind === 'unit'
      ? {
          from_unit: 'KG',
          to_unit: 'G',
          factor: '1000',
          output_scale: 2,
          rounding: 'HALF_UP',
          on_error: 'REJECT_ROW',
        }
      : null
  c.currency_conversion =
    kind === 'currency'
      ? {
          from_currency: 'USD',
          to_currency: 'IDR',
          rate: '1',
          rate_date: new Date().toISOString().slice(0, 10),
          rate_reference: '',
          output_scale: 2,
          rounding: 'HALF_UP',
          on_error: 'REJECT_ROW',
        }
      : null
}
function conversionKind(c: Column) {
  return c.unit_conversion ? 'unit' : c.currency_conversion ? 'currency' : 'none'
}
watch(
  draft,
  () => {
    checkedColumns.value = []
    checkedSections.value = []
    preview.value = null
  },
  { deep: true },
)
watch(
  resolved,
  () => {
    checkedColumns.value = []
    checkedSections.value = []
  },
  { deep: true },
)
watch(
  [user, configId],
  () => {
    generation++
    clearTimeout(timer)
    details.value = null
    draft.value = null
    preview.value = null
    job.value = null
    rollbackAcknowledged.value = false
    if (user.value && [...editRoles, ...reviewRoles].includes(user.value.role)) void run(load)
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  generation++
  clearTimeout(timer)
  window.removeEventListener('beforeunload', beforeUnload)
})
function beforeUnload(event: BeforeUnloadEvent) {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
window.addEventListener('beforeunload', beforeUnload)
function confirmLeave() {
  return !dirty.value || window.confirm('Perubahan draft belum disimpan. Tinggalkan halaman ini?')
}
onBeforeRouteLeave(confirmLeave)
onBeforeRouteUpdate(confirmLeave)
</script>

<template>
  <EtlShell>
    <RouterLink to="/workspace">← Daftar sumber</RouterLink>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success" role="status">{{ notice }}</p>
    <details v-if="parameterCatalog" class="panel">
      <summary>Parameter runtime dan capability (BE12)</summary>
      <p class="muted">
        Parameter bertanda supported=false hanya didokumentasikan dan tidak dikirim oleh editor.
      </p>
      <pre>{{ JSON.stringify(parameterCatalog, null, 2) }}</pre>
    </details>
    <p v-if="busy" aria-live="polite"><Spinner label="Memproses…" /></p>
    <template v-if="busy && !details">
      <CardSkeleton :rows="2" />
      <CardSkeleton :rows="4" />
      <CardSkeleton :rows="3" />
    </template>
    <template v-if="details && draft && record">
      <p class="eyebrow">{{ details.source.name }} / {{ details.sheet.sheet_name }}</p>
      <h1>Verifikasi konfigurasi ETL</h1>
      <div class="toolbar">
        <span class="tag">{{ record.status }}</span
        ><span>Versi {{ record.version_no }} · revisi {{ record.revision_no }}</span
        ><span class="muted">Keyakinan AI {{ Math.round(draft.overall_confidence * 100) }}%</span
        ><span v-if="dirty" class="tag">Perubahan belum disimpan</span>
      </div>
      <p class="notice">
        Periksa rekomendasi AI, jawab pertanyaan, lalu jalankan dry-run. Persetujuan mengacu pada
        revisi dan snapshot yang diperiksa.
      </p>
      <details>
        <summary>Parameter template yang belum didukung</summary>
        <p v-for="item in details.capabilities.unsupported" :key="item">• {{ item }}</p>
        <p>
          Sel referensi dan parameter tersebut dilindungi pada Excel. Klasifikasi master dan
          pembuatan relasi otomatis belum dijalankan oleh alur ini.
        </p>
      </details>
      <SheetClassification
        :key="record.source_sheet_id"
        :sheet-id="record.source_sheet_id"
        :source-id="record.source_id"
        :active="!!details.sheet.active_configuration_id"
        :disabled="busy || dirty"
        @changed="run(load)"
      />
      <p
        v-if="!evidenceReady && ['NEEDS_REVIEW', 'APPROVED', 'SUPERSEDED'].includes(record.status)"
        class="notice"
      >
        Bukti klasifikasi tidak sesuai revisi terbaru. Untuk draft, periksa ulang lalu ajukan
        review. Untuk versi approved/superseded, clone ke draft sebelum review ulang.
      </p>
      <nav class="steps" aria-label="Tahapan review">
        <button
          v-for="(label, i) in sectionLabels"
          :key="label"
          :class="{ active: step === i }"
          :aria-current="step === i ? 'step' : undefined"
          @click="step = i"
        >
          {{ i + 1 }}. {{ label }}</button
        ><button :class="{ active: step === 6 }" @click="step = 6">
          7. Validasi &amp; persetujuan
        </button>
      </nav>
      <fieldset :disabled="!canEdit || busy" class="panel" v-show="step < 6">
        <template v-if="step === 0"
          ><h2>Identitas dataset</h2>
          <div class="grid">
            <label
              >Nama bisnis<input
                v-model="draft.dataset_business_name"
                maxlength="200"
                required /></label
            ><label>Kode produk data<input v-model="draft.semantic.code" required /></label>
          </div>
          <label
            >Deskripsi<textarea
              v-model="draft.dataset_description"
              rows="3"
              maxlength="2000"
            /></label
          ><label
            >Makna satu baris / grain<textarea
              v-model="draft.grain"
              rows="2"
              maxlength="500"
              placeholder="Contoh: satu baris per transaksi per produk"
            />
          </label>
        </template>
        <template v-if="step === 1"
          ><h2>Pemetaan kolom &amp; sensitivitas</h2>
          <p class="muted">
            Primary/business key wajib tidak nullable. Data MEDIUM/HIGH disembunyikan dari produk
            analitik. Perubahan nama kolom perlu disesuaikan pada aturan kualitas dan metrik.
          </p>
          <div v-for="(c, i) in draft.columns" :key="i" class="card-row">
            <h3>
              {{ c.source_column }} <span class="tag">{{ Math.round(c.confidence * 100) }}%</span>
            </h3>
            <p class="muted">{{ c.reason }}</p>
            <div class="grid">
              <label>Nama bisnis<input v-model="c.business_name" /></label
              ><label>Kolom database<input v-model="c.target_column" maxlength="63" /></label
              ><label
                >Tipe<select v-model="c.target_type">
                  <option v-for="t in types" :key="t">{{ t }}</option>
                </select></label
              ><label
                >Sensitivitas<select v-model="c.pii_classification">
                  <option v-for="p in ['NONE', 'LOW', 'MEDIUM', 'HIGH']" :key="p">{{ p }}</option>
                </select></label
              >
            </div>
            <div class="toolbar">
              <label class="check"><input type="checkbox" v-model="c.nullable" />Boleh kosong</label
              ><label class="check"
                ><input type="checkbox" v-model="c.is_business_key" />Business key</label
              ><label class="check"
                ><input type="checkbox" v-model="c.is_primary_key" />Primary key</label
              ><button
                class="danger"
                :disabled="draft.columns.length === 1"
                @click="draft.columns.splice(i, 1)"
              >
                Hapus mapping
              </button>
            </div>
            <label>Catatan / alasan<textarea v-model="c.reason" rows="2" /></label>
            <details>
              <summary>Parameter tipe &amp; presisi (BE-12)</summary>
              <div class="grid">
                <label v-if="c.target_type === 'numeric'"
                  >Precision<input
                    type="number"
                    min="1"
                    max="100"
                    :value="c.numeric_precision"
                    @change="
                      c.numeric_precision =
                        ($event.target as HTMLInputElement).value === ''
                          ? null
                          : Number(($event.target as HTMLInputElement).value)
                    "
                /></label>
                <label v-if="c.target_type === 'numeric'"
                  >Scale<input
                    type="number"
                    min="0"
                    max="50"
                    :value="c.numeric_scale"
                    @change="
                      c.numeric_scale =
                        ($event.target as HTMLInputElement).value === ''
                          ? null
                          : Number(($event.target as HTMLInputElement).value)
                    "
                /></label>
                <label v-if="c.target_type === 'text' || c.target_type === 'varchar'"
                  >Panjang varchar<input
                    type="number"
                    min="1"
                    max="10485760"
                    :value="c.varchar_length"
                    @change="
                      c.varchar_length =
                        ($event.target as HTMLInputElement).value === ''
                          ? null
                          : Number(($event.target as HTMLInputElement).value)
                    "
                /></label>
                <label v-if="c.target_type === 'date'"
                  >Pola tanggal (strptime)<input
                    v-model="c.date_format"
                    maxlength="40"
                    placeholder="%d/%m/%Y"
                /></label>
                <label v-if="c.target_type === 'numeric'"
                  >Locale angka<select
                    :value="c.number_locale || ''"
                    @change="c.number_locale = ($event.target as HTMLSelectElement).value || null"
                  >
                    <option value="">(tidak diatur)</option>
                    <option v-for="l in numberLocales" :key="l">{{ l }}</option>
                  </select></label
                >
                <label v-if="c.target_type === 'timestamptz'"
                  >Timezone sumber (IANA)<input
                    v-model="c.source_timezone"
                    maxlength="100"
                    placeholder="Asia/Jakarta"
                /></label>
              </div>
              <p class="muted">
                Kosongkan field yang tidak dipakai. Precision/scale/varchar hanya berlaku untuk tipe
                kolom yang sesuai; date_format dan number_locale memerlukan transform parse_date_id
                / parse_decimal_id pada kolom ini.
              </p>
              <template v-if="c.target_type === 'numeric'">
                <h4>Konversi satuan/kurs</h4>
                <label
                  >Jenis konversi<select
                    :value="conversionKind(c)"
                    @change="
                      setConversion(
                        c,
                        ($event.target as HTMLSelectElement).value as 'none' | 'unit' | 'currency',
                      )
                    "
                  >
                    <option value="none">Tidak ada</option>
                    <option value="unit">Satuan</option>
                    <option value="currency">Mata uang</option>
                  </select></label
                >
                <div v-if="c.unit_conversion" class="grid">
                  <label
                    >Dari<select v-model="c.unit_conversion.from_unit">
                      <option v-for="u in units" :key="u">{{ u }}</option>
                    </select></label
                  ><label
                    >Ke<select v-model="c.unit_conversion.to_unit">
                      <option v-for="u in units" :key="u">{{ u }}</option>
                    </select></label
                  ><label
                    >Faktor<input v-model="c.unit_conversion.factor" placeholder="1000" /></label
                  ><label
                    >Skala output<input
                      type="number"
                      min="0"
                      max="50"
                      v-model.number="c.unit_conversion.output_scale"
                  /></label>
                  <label
                    >Pembulatan<select v-model="c.unit_conversion.rounding">
                      <option v-for="r in roundings" :key="r">{{ r }}</option>
                    </select></label
                  >
                </div>
                <div v-if="c.currency_conversion" class="grid">
                  <label
                    >Dari<select v-model="c.currency_conversion.from_currency">
                      <option v-for="cur in currencies" :key="cur">{{ cur }}</option>
                    </select></label
                  ><label
                    >Ke<select v-model="c.currency_conversion.to_currency">
                      <option v-for="cur in currencies" :key="cur">{{ cur }}</option>
                    </select></label
                  ><label>Kurs (string desimal)<input v-model="c.currency_conversion.rate" /></label
                  ><label
                    >Tanggal kurs<input type="date" v-model="c.currency_conversion.rate_date"
                  /></label>
                  <label
                    >Referensi kurs<input
                      v-model="c.currency_conversion.rate_reference"
                      maxlength="500"
                  /></label>
                  <label
                    >Skala output<input
                      type="number"
                      min="0"
                      max="50"
                      v-model.number="c.currency_conversion.output_scale"
                  /></label>
                  <label
                    >Pembulatan<select v-model="c.currency_conversion.rounding">
                      <option v-for="r in roundings" :key="r">{{ r }}</option>
                    </select></label
                  >
                </div>
                <p v-if="c.unit_conversion || c.currency_conversion" class="muted">
                  Kirim faktor/kurs sebagai string agar presisi desimal tidak hilang. on_error
                  selalu REJECT_ROW.
                </p>
              </template>
            </details>
          </div>
          <div v-if="unusedHeaders.length" class="toolbar">
            <select v-model="selectedHeader" aria-label="Header untuk ditambahkan">
              <option value="">Pilih header tambahan</option>
              <option v-for="h in unusedHeaders" :key="h.source_column">
                {{ h.source_column }}
              </option></select
            ><button :disabled="!selectedHeader || draft.columns.length >= 100" @click="addColumn">
              Tambah mapping
            </button>
          </div>
        </template>
        <template v-if="step === 2"
          ><h2>Urutan cleansing</h2>
          <p class="muted">
            Transformasi berjalan dari atas ke bawah pada setiap kolom. Tidak ada koreksi ejaan
            otomatis tanpa aturan yang disetujui.
          </p>
          <div v-for="(c, index) in draft.columns" :key="index" class="card-row">
            <h3>{{ c.source_column }} → {{ c.target_column }}</h3>
            <div v-for="(_, i) in c.transformation_codes" :key="i" class="toolbar">
              <span>{{ i + 1 }}.</span
              ><select
                v-model="c.transformation_codes[i]"
                :aria-label="`Transformasi ${c.source_column} urutan ${i + 1}`"
              >
                <option v-for="t in transforms" :key="t">{{ t }}</option></select
              ><button
                :disabled="i === 0"
                @click="
                  c.transformation_codes.splice(i - 1, 0, c.transformation_codes.splice(i, 1)[0]!)
                "
              >
                Naik</button
              ><button
                :disabled="i === c.transformation_codes.length - 1"
                @click="
                  c.transformation_codes.splice(i + 1, 0, c.transformation_codes.splice(i, 1)[0]!)
                "
              >
                Turun</button
              ><button @click="c.transformation_codes.splice(i, 1)">Hapus</button>
            </div>
            <button
              :disabled="c.transformation_codes.length >= 10"
              @click="c.transformation_codes.push('trim')"
            >
              Tambah langkah
            </button>
          </div>
        </template>
        <template v-if="step === 3"
          ><h2>Aturan kualitas data</h2>
          <p v-if="!draft.data_quality_rules.length">
            Belum ada aturan tambahan. Pemeriksaan tipe, nullability, dan key tetap dijalankan.
          </p>
          <div v-for="(q, i) in draft.data_quality_rules" :key="i" class="card-row">
            <div class="grid">
              <label
                >Kolom<select v-model="q.column">
                  <option v-for="c in draft.columns" :key="c.target_column">
                    {{ c.target_column }}
                  </option>
                </select></label
              >
              <label
                >Aturan<select
                  v-model="q.rule"
                  @change="
                    q.value = q.rule === 'allowed_values' ? [] : q.rule === 'format' ? 'UUID' : null
                  "
                >
                  <option v-for="r in qualityRules" :key="r">
                    {{ r }}
                  </option>
                </select></label
              >
              <label v-if="q.rule === 'min' || q.rule === 'max'"
                >Batas angka<input
                  type="number"
                  step="any"
                  :value="q.value"
                  @input="qualityValue(q, $event)"
              /></label>
              <label v-if="q.rule === 'allowed_values'"
                >Nilai yang diizinkan (satu per baris)<textarea
                  :value="Array.isArray(q.value) ? q.value.join('\n') : ''"
                  @input="qualityValue(q, $event)"
                />
              </label>
              <label v-if="q.rule === 'format'"
                >Format<select v-model="q.value">
                  <option v-for="f in dqFormats" :key="f">{{ f }}</option>
                </select></label
              >
              <label v-if="q.rule === 'max_age_days'"
                >Umur maksimum (hari)<input
                  type="number"
                  min="0"
                  max="36500"
                  v-model.number="q.max_age_days"
              /></label>
              <label
                >Jika gagal<select v-model="q.action_on_fail">
                  <option
                    v-for="a in ['REJECT_ROW', 'WARN', 'STOP_BATCH', 'REQUIRE_REVIEW']"
                    :key="a"
                  >
                    {{ a }}
                  </option>
                </select></label
              >
              <label
                >Severity<select v-model="q.severity">
                  <option v-for="s in dqSeverities" :key="s">{{ s }}</option>
                </select></label
              >
              <label
                >Owner<input v-model="q.owner" maxlength="100" placeholder="(opsional)"
              /></label>
              <label
                >Threshold gagal (%)<input
                  type="number"
                  min="0"
                  max="100"
                  step="any"
                  :value="q.threshold_percent"
                  @change="
                    q.threshold_percent =
                      ($event.target as HTMLInputElement).value === ''
                        ? null
                        : Number(($event.target as HTMLInputElement).value)
                  "
              /></label>
              <label
                >Default value (JSON scalar)<input
                  :value="defaultValueText(q)"
                  @change="defaultValueInput(q, $event)"
                  placeholder='0, false, "teks", null'
              /></label>
            </div>
            <button class="danger" @click="draft.data_quality_rules.splice(i, 1)">
              Hapus aturan
            </button>
          </div>
          <button :disabled="draft.data_quality_rules.length >= 100" @click="addQuality">
            Tambah aturan
          </button>
        </template>
        <template v-if="step === 4"
          ><h2>Target &amp; strategi pemuatan</h2>
          <div class="grid">
            <label>Schema<input :value="draft.target_schema" disabled /></label
            ><label
              >Nama dasar tabel<input
                v-model="draft.target_table"
                maxlength="30"
                pattern="[a-z][a-z0-9_]*" /></label
            ><label
              >Strategi<select v-model="draft.load_strategy">
                <option>UPSERT</option>
                <option>APPEND</option>
                <option>FULL_REFRESH</option>
              </select></label
            >
          </div>
          <p v-if="draft.load_strategy === 'UPSERT'" class="notice">
            Baris dengan key yang sama diperbarui; key baru ditambahkan. Pastikan business key
            stabil dan unik.
          </p>
          <p v-else-if="draft.load_strategy === 'APPEND'" class="notice">
            Baris ditambahkan pada pemuatan berikutnya. Pastikan strategi sesuai dengan sumber
            snapshot agar data tidak berulang.
          </p>
          <p v-else class="notice">
            Isi target diganti saat pemuatan berhasil. Pastikan spreadsheet berisi seluruh data yang
            ingin dipertahankan.
          </p>
        </template>
        <template v-if="step === 5"
          ><h2>Dimensi, metrik &amp; akses</h2>
          <h3>Dimensi</h3>
          <div class="toolbar">
            <label v-for="c in publicColumns" :key="c.target_column" class="check"
              ><input
                type="checkbox"
                v-model="draft.semantic.dimensions"
                :value="c.target_column"
              />{{ c.target_column }}</label
            >
          </div>
          <h3>Metrik</h3>
          <div v-for="(m, i) in draft.semantic.metrics" :key="i" class="card-row">
            <div class="grid">
              <label>Kode metrik<input v-model="m.code" /></label
              ><label>Label<input v-model="m.label" /></label
              ><label
                >Kolom<select v-model="m.column">
                  <option v-for="c in publicColumns" :key="c.target_column">
                    {{ c.target_column }}
                  </option>
                </select></label
              ><label
                >Agregasi<select v-model="m.aggregation">
                  <option
                    v-for="a in ['sum', 'count', 'avg', 'min', 'max', 'count_distinct']"
                    :key="a"
                  >
                    {{ a }}
                  </option>
                </select></label
              >
            </div>
            <button class="danger" @click="draft.semantic.metrics.splice(i, 1)">
              Hapus metrik
            </button>
          </div>
          <button
            @click="
              draft.semantic.metrics.push({
                code: '',
                label: '',
                column: publicColumns[0]?.target_column || '',
                aggregation: 'count',
              })
            "
          >
            Tambah metrik
          </button>
          <h3>Akun yang dapat mengakses produk analitik</h3>
          <div class="toolbar">
            <label v-for="r in roles" :key="r" class="check"
              ><input type="checkbox" v-model="draft.semantic.allowed_roles" :value="r" />{{
                r
              }}</label
            >
          </div>
        </template>
      </fieldset>
      <section v-if="step === 6" class="panel">
        <h2>Hasil dry-run</h2>
        <p :class="details.validation.valid ? 'success' : 'error'">
          {{
            details.validation.valid
              ? 'Snapshot lolos validasi.'
              : 'Masih ada pertanyaan atau kesalahan yang perlu diselesaikan.'
          }}
          {{ details.validation.sample_rows_valid ?? 0 }} baris valid ·
          {{ details.validation.sample_rows_invalid ?? 0 }} baris bermasalah.
        </p>
        <p v-for="(e, i) in details.validation.errors" :key="i" class="error">{{ e.message }}</p>
        <p class="muted">
          Hasil berasal dari snapshot profiling terakhir; data sensitif disamarkan. Deployment juga
          memeriksa apakah isi Google Sheet berubah sejak review.
        </p>
        <div class="scroll">
          <table v-if="details.validation.row_previews?.length">
            <thead>
              <tr>
                <th>Baris</th>
                <th>Sebelum</th>
                <th>Sesudah</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in details.validation.row_previews" :key="r.source_row">
                <td>{{ r.source_row }}</td>
                <td>
                  <div v-for="(v, k) in r.before" :key="k">
                    <b>{{ k }}:</b> {{ v ?? '∅' }}
                  </div>
                </td>
                <td>
                  <div v-for="(v, k) in r.after" :key="k">
                    <b>{{ k }}:</b> {{ v ?? '∅' }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <details
          v-if="details.validation.issues?.length || details.validation.warnings?.length"
          open
        >
          <summary>Temuan validasi</summary>
          <pre>{{
            JSON.stringify(
              { issues: details.validation.issues, warnings: details.validation.warnings },
              null,
              2,
            )
          }}</pre>
        </details>
        <details>
          <summary>Rencana tabel &amp; view</summary>
          <pre>{{ JSON.stringify(details.validation.deployment_plan, null, 2) }}</pre>
        </details>
        <fieldset :disabled="!canEdit || dirty || busy">
          <h3>Pernyataan verifikasi</h3>
          <p class="muted">
            Centang setelah memeriksa setiap bagian dan kolom. Perubahan draft membatalkan checklist
            ini.
          </p>
          <div class="grid">
            <div>
              <label v-for="(s, i) in sections" :key="s" class="check"
                ><input type="checkbox" v-model="checkedSections" :value="s" />{{
                  sectionLabels[i]
                }}
                sudah diperiksa</label
              >
            </div>
            <div>
              <label v-for="c in draft.columns" :key="c.source_column" class="check"
                ><input type="checkbox" v-model="checkedColumns" :value="c.target_column" />{{
                  c.source_column
                }}
                → {{ c.target_column }}</label
              >
            </div>
          </div>
          <button class="primary" :disabled="!ready" @click="run(submit)">
            Ajukan review revisi {{ record.revision_no }}
          </button>
        </fieldset>
        <p v-if="submitted" class="success">Revisi ini sudah diajukan untuk review.</p>
        <div v-if="reviewer && record.status === 'NEEDS_REVIEW'" class="card-row">
          <h3>Keputusan approver</h3>
          <p class="muted">
            Periksa seluruh tahapan dan hasil dry-run sebelum memberikan keputusan.
          </p>
          <p v-if="record.created_by === user?.id" class="notice">
            Gunakan akun approver berbeda untuk menyetujui draft ini.
          </p>
          <div class="toolbar">
            <button
              class="primary"
              :disabled="
                busy ||
                dirty ||
                !submitted ||
                !details.validation.ready_for_review ||
                record.created_by === user?.id
              "
              @click="
                comment = ''
                decisionModal = 'approve'
              "
            >
              Setujui konfigurasi</button
            ><button
              :disabled="busy || dirty"
              @click="
                comment = ''
                decisionModal = 'reject'
              "
            >
              Tolak konfigurasi
            </button>
          </div>
        </div>
      </section>
      <Modal
        :open="decisionModal !== null"
        :title="decisionModal === 'approve' ? 'Setujui konfigurasi' : 'Tolak konfigurasi'"
        @close="decisionModal = null"
      >
        <p class="muted">
          {{
            decisionModal === 'approve'
              ? 'Persetujuan mengacu pada revisi dan snapshot yang sudah diperiksa. Deployment tetap perlu dijalankan terpisah.'
              : 'Konfigurasi yang ditolak dapat di-clone untuk perbaikan.'
          }}
        </p>
        <label>Catatan keputusan<textarea v-model="comment" maxlength="2000" rows="4" /></label>
        <template #footer>
          <button :disabled="busy" @click="decisionModal = null">Batal</button>
          <button
            :class="{ primary: decisionModal === 'approve' }"
            :disabled="busy"
            @click="run(() => decision(decisionModal as 'approve' | 'reject'))"
          >
            <Spinner v-if="busy" :size="14" /><CircleCheck
              v-else-if="decisionModal === 'approve'"
              class="icon"
              :size="14"
            /><CircleX v-else class="icon" :size="14" />
            {{ decisionModal === 'approve' ? 'Konfirmasi setuju' : 'Konfirmasi tolak' }}
          </button>
        </template>
      </Modal>
      <Card
        v-if="
          draft.unresolved_questions.length ||
          Object.keys(record.review_state?.answers || {}).length
        "
        title="Pertanyaan & klarifikasi"
      >
        <fieldset :disabled="!canEdit || busy">
          <div v-for="q in draft.unresolved_questions" :key="q" class="question">
            <label
              >{{ q
              }}<textarea
                v-model="answers[q]"
                maxlength="2000"
                placeholder="Jelaskan keputusan bisnis Anda"
              /></label
            ><label class="check"
              ><input
                type="checkbox"
                v-model="resolved"
                :value="q"
                :disabled="!answers[q]?.trim()"
              />Selesai — perubahan konfigurasi terkait sudah saya sesuaikan</label
            >
          </div>
        </fieldset>
        <details v-if="Object.keys(record.review_state?.answers || {}).length">
          <summary>Jawaban tersimpan</summary>
          <p v-for="(a, q) in record.review_state.answers" :key="q">
            <strong>{{ q }}</strong
            ><br />{{ a.answer }}
          </p>
        </details>
      </Card>
      <details class="panel">
        <summary>Review melalui Excel (opsional)</summary>
        <p>
          Unduh draft terbaru, edit sel kuning, lalu unggah untuk melihat perubahan. Impor menyimpan
          draft dan tetap memerlukan verifikasi serta persetujuan aplikasi.
        </p>
        <div class="toolbar">
          <button :disabled="busy || dirty" @click="run(download)">
            <Download class="icon" :size="14" />Unduh template terisi (.xlsx)</button
          ><label v-if="canEdit"
            ><span class="toolbar"><Upload class="icon" :size="14" />Unggah untuk preview</span
            ><input type="file" accept=".xlsx" :disabled="busy || dirty" @change="importFile"
          /></label>
        </div>
        <div v-if="preview">
          <p v-for="(e, i) in preview.errors" :key="i" class="error">
            {{ e.location }}: {{ e.message }}
          </p>
          <p v-if="preview.can_apply" class="notice">
            Preview siap disimpan sebagai draft.
            {{
              preview.validation?.valid
                ? 'Dry-run lolos.'
                : 'Masih diperlukan perbaikan atau jawaban sebelum approval.'
            }}
          </p>
          <p v-if="preview.can_apply && !Object.keys(preview.diff).length">
            Tidak ada perubahan konfigurasi.
          </p>
          <details v-for="(change, key) in preview.diff" :key="key" open>
            <summary>{{ key }}</summary>
            <div class="grid">
              <div>
                <b>Sebelum</b>
                <pre>{{ JSON.stringify(change.before, null, 2) }}</pre>
              </div>
              <div>
                <b>Sesudah</b>
                <pre>{{ JSON.stringify(change.after, null, 2) }}</pre>
              </div>
            </div>
          </details>
          <p v-for="(answer, q) in preview.question_answers" :key="q">{{ q }}: {{ answer }}</p>
          <button
            class="primary"
            :disabled="busy || dirty || !preview.can_apply"
            @click="run(applyWorkbook)"
          >
            Terima perubahan Excel ke draft
          </button>
        </div>
      </details>
      <ConfigurationHistory :config="record" :disabled="busy || dirty" />
      <Card v-if="reviewer && record.status === 'SUPERSEDED'" title="Rollback konfigurasi">
        <p class="notice">
          Mengaktifkan versi ini mengganti konfigurasi aktif. Ini tidak memulihkan data historis.
          Snapshot yang disetujui akan diperiksa ulang.
        </p>
        <label class="check"
          ><input v-model="rollbackAcknowledged" type="checkbox" :disabled="busy" />Saya sudah
          memeriksa versi yang akan diaktifkan kembali.</label
        ><button
          :disabled="busy || !rollbackAcknowledged || !evidenceReady"
          @click="run(() => queue(`${base}/rollback`))"
        >
          Antrekan rollback versi ini
        </button>
      </Card>
      <Card v-if="job" :title="`Proses: ${job.status}`">
        <p>{{ job.id }}</p>
        <RouterLink class="button" :to="{ path: '/jobs', query: { job: job.id } }"
          >Buka monitor job</RouterLink
        >
        <p v-if="job.status === 'QUEUED'" class="notice">Menunggu worker backend.</p>
        <p v-if="job.status === 'FAILED'" class="error">
          {{ job.error_code }} {{ job.error_message }}
        </p>
        <details v-if="job.result">
          <summary>Hasil proses</summary>
          <pre>{{ JSON.stringify(job.result, null, 2) }}</pre>
        </details>
      </Card>
      <div class="toolbar sticky-actions">
        <button v-if="step > 0" @click="step--">Sebelumnya</button
        ><button v-if="step < 6" @click="step++">Berikutnya</button
        ><button v-if="canEdit" class="primary" :disabled="busy || !dirty" @click="run(save)">
          <Spinner v-if="busy" :size="14" /><Save v-else class="icon" :size="14" />Simpan draft</button
        ><button :disabled="busy || dirty" @click="run(validate)">
          <RefreshCw class="icon" :size="14" />Dry-run ulang
        </button>
        <button v-if="dirty" :disabled="busy" @click="run(load)">
          Buang perubahan &amp; muat ulang
        </button>
        <button v-if="editor && !isDraft" :disabled="busy" @click="run(clone)">
          <Copy class="icon" :size="14" />Clone untuk perbaikan
        </button>
        <button
          v-if="reviewer && record.status === 'APPROVED'"
          class="primary"
          :disabled="busy || !evidenceReady"
          @click="run(() => queue(`${base}/deploy`))"
        >
          <Rocket class="icon" :size="14" />Deploy konfigurasi
        </button>
        <button
          v-if="editor && record.status === 'ACTIVE'"
          class="primary"
          :disabled="busy"
          @click="run(syncReview)"
        >
          <GitBranch class="icon" :size="14" />Buat batch sync review
        </button>
      </div>
    </template>
  </EtlShell>
</template>
