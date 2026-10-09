<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EtlShell from '@/components/EtlShell.vue'
import DataTable from '@/components/DataTable.vue'
import { call, user, editRoles, reviewRoles } from '@/lib/etl'
import { createImportReview } from '@/lib/importReviews'
import type { MasterSourceBindings } from '@/lib/masters'
import { useTask } from '@/lib/tasks'

interface StoragePlan {
  target: string
  master_version: number
  revision_no: number
  ddl: string
  schema_policy: string
  execution_ready: false
}
interface RecordsPage {
  items: Record<string, unknown>[]
  has_more: boolean
  masked_fields: string[]
}
const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))
const reviewer = computed(() => reviewRoles.includes(user.value?.role || ''))
const reader = computed(() => [...editRoles, ...reviewRoles].includes(user.value?.role || ''))
const { busy, error, notice, run } = useTask()
const plan = ref<StoragePlan | null>(null)
const bindings = ref<MasterSourceBindings | null>(null)
const records = ref<RecordsPage | null>(null)
const search = ref(''),
  recordId = ref(''),
  activeOnly = ref(true),
  offset = ref(0)
const applied = ref({ search: '', recordId: '', activeOnly: true })
const comment = ref(''),
  confirmed = ref(false)
let generation = 0
const base = () => `/master-definitions/${encodeURIComponent(id.value)}`
async function loadPlan() {
  const current = generation
  plan.value = null
  confirmed.value = false
  const result = await call<StoragePlan>('GET', `${base()}/storage-plan`)
  if (current === generation) plan.value = result
}
async function loadBindings() {
  const current = generation
  bindings.value = null
  const result = await call<MasterSourceBindings>('GET', `${base()}/source-bindings`)
  if (current === generation) bindings.value = result
}
async function startImport(sourceSheetId: string) {
  const result = await createImportReview(sourceSheetId)
  await router.push(`/import-reviews/${result.review.id}`)
}
async function loadRecords(next = 0, apply = false) {
  const current = generation
  if (apply)
    applied.value = {
      search: search.value,
      recordId: recordId.value.trim(),
      activeOnly: activeOnly.value,
    }
  const filters = applied.value
  const params = new URLSearchParams({
    search: filters.search,
    offset: String(next),
    limit: '50',
    active_only: String(filters.activeOnly),
  })
  if (filters.recordId) params.set('record_id', filters.recordId)
  records.value = null
  const result = await call<RecordsPage>('GET', `${base()}/records?${params}`)
  if (current === generation) {
    records.value = result
    offset.value = next
  }
}
async function deploy() {
  if (!reviewer.value || !plan.value || !confirmed.value) return
  const current = generation
  const revision = plan.value.revision_no
  confirmed.value = false
  records.value = null
  // Consume the reviewed plan even on failure: refresh before an explicit retry.
  plan.value = null
  const result = await call<{ storage_ready: boolean; execution_ready: false }>(
    'POST',
    `${base()}/deploy-storage`,
    { revision_no: revision, comment: comment.value.trim() },
  )
  if (current !== generation) return
  notice.value = result.storage_ready
    ? 'Storage siap. Pilih tab terikat di bawah untuk membuat batch review/import master.'
    : 'Periksa kesiapan storage kembali.'
  await loadPlan()
  await loadBindings()
  if (current === generation) await loadRecords(0)
}
let pendingLoad = false
function initialize() {
  if (!pendingLoad || busy.value || !reader.value) return
  pendingLoad = false
  const current = generation
  void run(async () => {
    await Promise.all([loadPlan(), loadBindings()])
    if (current === generation && plan.value) await loadRecords()
  })
}
watch(
  [id, user],
  () => {
    ++generation
    plan.value = null
    bindings.value = null
    records.value = null
    confirmed.value = false
    comment.value = ''
    search.value = ''
    recordId.value = ''
    activeOnly.value = true
    offset.value = 0
    applied.value = { search: '', recordId: '', activeOnly: true }
    pendingLoad = true
    initialize()
  },
  { immediate: true },
)
watch(busy, () => initialize())
onBeforeUnmount(() => {
  ++generation
  pendingLoad = false
})
</script>

<template>
  <EtlShell>
    <RouterLink :to="`/masters/${id}`">← Definisi master</RouterLink>
    <h1>Storage &amp; record master</h1>
    <p class="notice">
      Import master memakai batch terpisah dari konfigurasi ETL biasa. Setiap tab harus memiliki
      binding approved dan storage siap; batch tetap memerlukan preview, approval, lalu apply.
    </p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <section class="panel">
      <h2>Rencana storage</h2>
      <button :disabled="busy" @click="run(loadPlan)">Muat ulang rencana</button>
      <template v-if="plan">
        <p>Versi approved {{ plan.master_version }} · revisi registry {{ plan.revision_no }}</p>
        <p>
          Schema identik atau penambahan field nullable dapat diterapkan. Perubahan key, tipe,
          nullability, penghapusan dan field wajib memerlukan migrasi khusus.
        </p>
        <details>
          <summary>Detail teknis rencana</summary>
          <p>Target: {{ plan.target }} · {{ plan.schema_policy }}</p>
          <p>
            DDL ini menggambarkan target lengkap, bukan diff ALTER. Membaca rencana tidak membuat
            tabel.
          </p>
          <pre class="scroll">{{ plan.ddl }}</pre>
        </details>
        <form v-if="reviewer" @submit.prevent="run(deploy)">
          <label
            >Catatan deployment<textarea v-model="comment" :disabled="busy" maxlength="2000" />
          </label>
          <label
            ><input v-model="confirmed" type="checkbox" :disabled="busy" />Saya telah meninjau
            rencana versi approved ini.</label
          >
          <button class="primary" :disabled="busy || !confirmed">Deploy storage</button>
        </form>
        <p v-else class="muted">
          Deployment hanya tersedia bagi Platform Admin dan Technical Approver.
        </p>
      </template>
    </section>
    <section class="panel">
      <h2>Sumber master terikat</h2>
      <button :disabled="busy" @click="run(loadBindings)">Muat ulang sumber terikat</button>
      <p v-if="!bindings?.items.length" class="muted">
        Belum ada tab sumber yang terikat ke definisi master ini. Atur binding dari halaman sumber
        setelah profiling dan klasifikasi MASTER dikonfirmasi.
      </p>
      <div v-for="item in bindings?.items || []" :key="item.source_sheet_id" class="card-row">
        <div class="toolbar">
          <strong>{{ item.source_name }} · {{ item.sheet_name }}</strong>
          <span v-if="item.execution_ready">✓ Siap diimpor</span>
          <span v-else class="muted">Belum siap · {{ item.blocking_reason || 'MASTER_BINDING_REVIEW_REQUIRED' }}</span>
          <button
            v-if="editRoles.includes(user?.role || '')"
            class="primary"
            :disabled="busy || !item.execution_ready"
            @click="run(() => startImport(item.source_sheet_id))"
          >
            Buat batch review/import
          </button>
        </div>
        <p v-if="item.validation?.errors?.length" class="muted">
          {{ item.validation.errors.length }} masalah mapping/data perlu diselesaikan.
        </p>
      </div>
    </section>
    <section class="panel">
      <h2>Record kanonis</h2>
      <form class="toolbar" @submit.prevent="run(() => loadRecords(0, true))">
        <label>Cari business key atau label<input v-model="search" maxlength="200" /></label>
        <label
          >UUID record<input
            v-model="recordId"
            pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        /></label>
        <label><input v-model="activeOnly" type="checkbox" />Hanya record aktif</label>
        <button :disabled="busy">Cari record</button>
      </form>
      <p v-if="busy" role="status">Memuat…</p>
      <template v-if="records">
        <p v-if="records.masked_fields.length" class="notice">
          Field disamarkan oleh backend: {{ records.masked_fields.join(', ') }}. Nilai *** pada
          field tersebut adalah placeholder, termasuk untuk null.
        </p>
        <p v-if="!records.items.length">
          Tidak ada record untuk filter ini. Storage kosong tidak membuktikan import telah
          dilakukan.
        </p>
        <DataTable v-else :rows="records.items" />
        <div class="toolbar">
          <button
            :disabled="busy || offset === 0"
            @click="run(() => loadRecords(Math.max(0, offset - 50)))"
          >
            Record sebelumnya
          </button>
          <button
            :disabled="busy || !records.has_more"
            @click="run(() => loadRecords(offset + 50))"
          >
            Record berikutnya
          </button>
        </div>
        <p class="muted">
          Offset {{ offset }}, maksimal 50 record. Urutan UUID stabil; data dapat berubah
          antarhalaman. Pencarian hanya memakai field yang boleh dilihat akun ini.
        </p>
      </template>
    </section>
  </EtlShell>
</template>
