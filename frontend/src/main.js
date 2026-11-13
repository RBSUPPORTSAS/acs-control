import {
    createApp,
    ref,
    computed,
    onMounted,
    onUnmounted,
    watch
} from 'vue/dist/vue.esm-bundler.js'

import './style.css'

// ACS_TAGS_UI_08B


createApp({

    setup() {

        const devices = ref([])
        const loading = ref(true)
        const error = ref(null)
        const search = ref('')

        const health = ref({
            api: false,
            postgresql: false,
            redis: false,
            genieacs: false,
            healthy: false
        })

        // ACS_AUDIT_UI_10B
        const auditOpen = ref(false)
        const audits = ref([])
        const auditLoading = ref(false)

        const selectedDevice = ref(null)
        const detailLoading = ref(false)

        // Lectura de datos de la ONU bajo demanda (refreshObject, solo lectura)
        const dataStatus = ref(null)
        const certification = ref(null)
        // Modelo no certificado: solo se muestran datos, sin gestión.
        const readOnly = computed(() => certification.value?.certified === false)
        // '' | 'reading' | 'updating' | 'waiting' | 'done' | 'error'
        const refreshState = ref('')
        const refreshMessage = ref('')
        // Llegaron datos nuevos pero la pestaña no se recargó (formulario en uso)
        const refreshNewData = ref(false)
        let refreshToken = 0
        const activeTab = ref('resumen')

// ACS_TAGS_WRITE_UI_08D
const newTag = ref('')
const tagBusy = ref(false)

// ACS_WIFI_UI_06B
// ACS_WAN_UI_11B
const wan = ref(null)
const wanLoading = ref(false)
const wanError = ref(null)

// ACS_WAN_FORM_12D2
const wanFormOpen = ref(false)

// ACS_WAN_EDIT_UI_12F2
const wanEditing = ref(null)
const wanInterfaces = ref([])
const wanCreating = ref(false)

// ACS_WAN_TOGGLE_UI_12E2
const wanToggleBusy = ref(null)

// ACS_WAN_DELETE_UI_12G2
const wanDeleteBusy = ref(null)
const wanMessage = ref('')
// ACS_WAN_MULTITYPE_14A1
const wanForm = ref({
    type: 'pppoe',
    vlan: 110,
    priority: 0,

    username: '',
    password: '',

    ip: '',
    subnet_mask: '',
    gateway: '',
    dns: '',

    nat: true,
    mtu: 1492,
    bindings: []
})

const wifi = ref(null)
const wifiLoading = ref(false)
const wifiError = ref(null)

// ACS_CATV_UI_07B
const catv = ref(null)
const catvLoading = ref(false)
const catvError = ref(null)
const catvBusy = ref(false)

// ACS_CATV_WRITE_UI_09B

        let refreshTimer = null


        // ACS_DEVICE_CENTER_18B

        const activeView = ref('inicio')

        const inventoryStatus = ref('all')
        const inventoryManufacturer = ref('all')
        const inventoryModel = ref('all')
        const inventoryTag = ref('all')
        const inventoryAcs = ref('all')

        const selectedInventoryIds = ref([])


        // ====================================================
        // Estadísticas
        // ====================================================

        const total = computed(() => devices.value.length)

        const online = computed(() =>
            devices.value.filter(device => device.online).length
        )

        const offline = computed(() =>
            devices.value.filter(device => !device.online).length
        )

        const manufacturers = computed(() => {

            const values = devices.value
                .map(device => device.manufacturer)
                .filter(Boolean)

            return new Set(values).size
        })


        // Desglose por fabricante para la tarjeta "Fabricantes"
        const manufacturerBreakdownOpen = ref(false)

        const manufacturerBreakdown = computed(() => {

            const groups = {}

            for (const device of devices.value) {

                if (!device.manufacturer)
                    continue

                const g = groups[device.manufacturer]
                    || (groups[device.manufacturer] = {
                        name: device.manufacturer,
                        total: 0,
                        online: 0,
                        offline: 0
                    })

                g.total++

                if (device.online) g.online++
                else g.offline++
            }

            return Object.values(groups).sort(
                (a, b) => b.total - a.total
                    || String(a.name).localeCompare(String(b.name))
            )
        })


        // ====================================================
        // Filtro
        // ====================================================

                // ACS_UI_POLISH_17A2
        const refreshing = ref(false)
        const lastUpdated = ref(null)

        const configOpen = ref(false)
        const configLoading = ref(false)
        const configError = ref(null)
        const systemConfig = ref(null)


const manufacturerOptions = computed(() => {

            return [
                ...new Set(
                    devices.value
                        .map(
                            device =>
                                device.manufacturer
                        )
                        .filter(Boolean)
                )
            ].sort((a, b) =>
                String(a).localeCompare(
                    String(b)
                )
            )
        })


        const modelOptions = computed(() => {

            return [
                ...new Set(
                    devices.value
                        .map(
                            device =>
                                device.product_class
                        )
                        .filter(Boolean)
                )
            ].sort((a, b) =>
                String(a).localeCompare(
                    String(b)
                )
            )
        })


        const tagOptions = computed(() => {

            const values = []

            for (const device of devices.value) {

                const tags =
                    deviceTags(device)

                for (const tag of tags) {
                    values.push(tag)
                }
            }

            return [
                ...new Set(values)
            ].sort((a, b) =>
                String(a).localeCompare(
                    String(b)
                )
            )
        })


        const filteredDevices = computed(() => {

            const term =
                search.value
                    .trim()
                    .toLowerCase()

            return devices.value.filter(
                device => {

                    // ------------------------------------
                    // TEXTO
                    // ------------------------------------

                    if (term) {

                        const searchable = [
                            device.id,
                            device.manufacturer,
                            device.product_class,
                            device.serial_number,
                            device.software_version,
                            device.hardware_version,
                            device.oui,

                            device.ip,
                            device.ip_address,
                            device.ipAddress,

                            ...deviceTags(device)
                        ]

                        const textMatch =
                            searchable.some(
                                value =>
                                    String(
                                        value ?? ''
                                    )
                                    .toLowerCase()
                                    .includes(term)
                            )

                        if (!textMatch)
                            return false
                    }


                    // ------------------------------------
                    // ESTADO
                    // ------------------------------------

                    if (
                        inventoryStatus.value
                        === 'online'
                        && !device.online
                    ) {
                        return false
                    }

                    if (
                        inventoryStatus.value
                        === 'offline'
                        && device.online
                    ) {
                        return false
                    }


                    // ------------------------------------
                    // FABRICANTE
                    // ------------------------------------

                    if (
                        inventoryManufacturer.value
                        !== 'all'
                        &&
                        device.manufacturer
                        !== inventoryManufacturer.value
                    ) {
                        return false
                    }


                    // ------------------------------------
                    // MODELO
                    // ------------------------------------

                    if (
                        inventoryModel.value
                        !== 'all'
                        &&
                        device.product_class
                        !== inventoryModel.value
                    ) {
                        return false
                    }


                    // ------------------------------------
                    // TAG
                    // ------------------------------------

                    if (
                        inventoryTag.value
                        !== 'all'
                    ) {

                        const tags =
                            deviceTags(device)

                        if (
                            !tags.includes(
                                inventoryTag.value
                            )
                        ) {
                            return false
                        }
                    }


                    /*
                     * ACS:
                     *
                     * Actualmente todos pertenecen
                     * al GenieACS principal.
                     *
                     * Se deja preparado para
                     * Multi-GenieACS.
                     */

                    if (
                        inventoryAcs.value
                        !== 'all'
                        &&
                        inventoryAcs.value
                        !== 'primary'
                    ) {
                        return false
                    }


                    return true
                }
            )
        })


        const allVisibleSelected = computed(() => {

            if (!filteredDevices.value.length)
                return false

            return filteredDevices.value.every(
                device =>
                    selectedInventoryIds.value
                        .includes(device.id)
            )
        })


        function deviceTags(device) {

            if (!device)
                return []

            if (Array.isArray(device.tags)) {
                return device.tags
                    .map(String)
                    .filter(Boolean)
            }

            if (device.tags) {
                return [
                    String(device.tags)
                ]
            }

            return []
        }


        function deviceIp(device) {

            return (
                device?.ip_address
                || device?.ipAddress
                || device?.ip
                || '-'
            )
        }


        function deviceLastInform(device) {

            if (!device)
                return null

            return (
                device.last_inform
                || device.lastInform
                || device.last_seen
                || device.last_seen_at
                || device._lastInform
                || null
            )
        }


        function relativeTime(value) {

            if (!value)
                return 'Sin información'

            const date = new Date(value)

            if (
                Number.isNaN(
                    date.getTime()
                )
            ) {
                return String(value)
            }

            const seconds =
                Math.floor(
                    (
                        Date.now()
                        - date.getTime()
                    ) / 1000
                )

            if (seconds < 0)
                return 'Ahora'

            if (seconds < 60)
                return 'Hace unos segundos'

            const minutes =
                Math.floor(seconds / 60)

            if (minutes < 60)
                return `Hace ${minutes} min`

            const hours =
                Math.floor(minutes / 60)

            if (hours < 24)
                return `Hace ${hours} h`

            const days =
                Math.floor(hours / 24)

            if (days < 30)
                return `Hace ${days} d`

            return formatDate(value)
        }


        function clearInventoryFilters() {

            search.value = ''
            inventoryStatus.value = 'all'
            inventoryManufacturer.value = 'all'
            inventoryModel.value = 'all'
            inventoryTag.value = 'all'
            inventoryAcs.value = 'all'
        }


        function isInventorySelected(id) {

            return selectedInventoryIds.value
                .includes(id)
        }


        function toggleInventoryDevice(id) {

            if (
                selectedInventoryIds.value
                    .includes(id)
            ) {

                selectedInventoryIds.value =
                    selectedInventoryIds.value
                        .filter(
                            item => item !== id
                        )

            } else {

                selectedInventoryIds.value = [
                    ...selectedInventoryIds.value,
                    id
                ]
            }
        }


        function toggleAllVisible() {

            if (allVisibleSelected.value) {

                const visible =
                    new Set(
                        filteredDevices.value
                            .map(device => device.id)
                    )

                selectedInventoryIds.value =
                    selectedInventoryIds.value
                        .filter(
                            id => !visible.has(id)
                        )

                return
            }


            const ids =
                new Set(
                    selectedInventoryIds.value
                )

            for (
                const device
                of filteredDevices.value
            ) {
                ids.add(device.id)
            }

            selectedInventoryIds.value = [
                ...ids
            ]
        }


        function clearInventorySelection() {

            selectedInventoryIds.value = []
        }


        function openInventory() {

            activeView.value =
                'dispositivos'
        }


        // Abre Dispositivos con filtros (desde las tarjetas de Inicio)
        function openInventoryFiltered(filters = {}) {

            clearInventoryFilters()

            if (filters.status)
                inventoryStatus.value = filters.status

            if (filters.manufacturer)
                inventoryManufacturer.value = filters.manufacturer

            manufacturerBreakdownOpen.value = false
            activeView.value = 'dispositivos'
        }


        // ====================================================
        // API
        // ====================================================

        
        // Filtro de la auditoria: '' (todo), SESION, USUARIO u ONU
        const auditFilter = ref('')

        const AUDIT_FILTERS = [
            { value: '', label: 'Todo' },
            { value: 'SESION', label: 'Sesiones' },
            { value: 'USUARIO', label: 'Usuarios' },
            { value: 'ONU', label: 'ONUs' }
        ]

        const AUDIT_LABELS = {
            SESION_INICIO: 'Inicio de sesión',
            SESION_CIERRE: 'Cierre de sesión',
            SESION_FALLIDA: 'Intento de inicio fallido',
            SESION_BLOQUEADA: 'Inicio bloqueado por intentos',
            USUARIO_CREAR: 'Usuario creado',
            USUARIO_EDITAR: 'Usuario editado',
            USUARIO_CAMBIAR_ROL: 'Cambio de rol',
            USUARIO_CAMBIAR_CONTRASENA: 'Cambio de contraseña',
            USUARIO_ACTIVAR: 'Usuario activado',
            USUARIO_DESACTIVAR: 'Usuario desactivado',
            USUARIO_ELIMINAR: 'Usuario eliminado',
            ETIQUETA_AGREGAR: 'Etiqueta agregada',
            ETIQUETA_QUITAR: 'Etiqueta quitada',
            WIFI_EDITAR: 'Wi-Fi editado',
            CATV_ACTIVAR: 'CATV activado',
            CATV_DESACTIVAR: 'CATV desactivado',
            WAN_CREAR_PPPOE: 'WAN PPPoE creada',
            WAN_CREAR_DHCP: 'WAN DHCP creada',
            WAN_CREAR_ESTATICA: 'WAN estática creada',
            WAN_CREAR_VSOL_PPPOE: 'WAN PPPoE creada (VSOL)',
            WAN_CREAR_VSOL_DHCP: 'WAN DHCP creada (VSOL)',
            WAN_CREAR_VSOL_STATIC: 'WAN estática creada (VSOL)',
            WAN_EDITAR_PPPOE: 'WAN PPPoE editada',
            WAN_EDITAR_PPPOE_WCD: 'WAN PPPoE editada',
            WAN_EDITAR_IP: 'WAN IP editada',
            WAN_ELIMINAR_PPPOE: 'WAN PPPoE eliminada',
            WAN_ELIMINAR_WCD: 'WAN eliminada',
            SEGURIDAD_FIREWALL_NIVEL: 'Nivel de firewall',
            SEGURIDAD_SERVICIO: 'Servicio de seguridad'
        }

        function auditResultClass(result) {
            const r = String(result || '').toUpperCase()
            if (['OK', 'CONFIRMADO', 'ENVIADO'].includes(r)) return 'ok'
            if (['FALLIDO', 'ERROR'].includes(r)) return 'error'
            return ''
        }

        function auditLabel(action) {
            return AUDIT_LABELS[action] || action
        }

        function auditTargetType(type) {
            return { SESION: 'Sesión', USUARIO: 'Usuario', ONU: 'ONU' }[type] || type || '-'
        }

        async function setAuditFilter(value) {
            auditFilter.value = value
            await openAudit()
        }

        async function openAudit() {
            auditOpen.value = true
            auditLoading.value = true

            try {
                const tipo = auditFilter.value
                    ? `&tipo=${encodeURIComponent(auditFilter.value)}`
                    : ''

                const r = await fetch(
                    `/api/audit?limit=300${tipo}`,
                    { cache: 'no-store' }
                )

                if (!r.ok)
                    throw new Error(`HTTP ${r.status}`)

                const data = await r.json()
                audits.value = data.audits || []

            } catch (e) {
                console.error(e)
                alert('No fue posible consultar la auditoría.')
            } finally {
                auditLoading.value = false
            }
        }

        function closeAudit() {
            auditOpen.value = false
        }

        function auditValue(value) {
            if (value === null || value === undefined)
                return '-'

            if (typeof value === 'object') {
                const entries = Object.entries(value)
                    .filter(([, v]) => v !== null && v !== '')

                if (!entries.length)
                    return '-'

                return entries
                    .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
                    .join(' · ')
            }

            return String(value)
        }


async function loadHealth() {

            try {

                const response = await fetch('/api/health', {
                    cache: 'no-store'
                })

                health.value = await response.json()

            } catch (e) {

                health.value = {
                    api: false,
                    postgresql: false,
                    redis: false,
                    genieacs: false,
                    healthy: false
                }
            }
        }


        async function loadDevices(showLoader = true) {

            if (showLoader) {
                loading.value = true
            }

            error.value = null

            try {

                const response = await fetch(
                    '/api/devices?limit=2000',
                    {
                        cache: 'no-store'
                    }
                )

                if (!response.ok) {
                    throw new Error(
                        `HTTP ${response.status}`
                    )
                }

                const data = await response.json()

                devices.value = data.devices || []

            } catch (e) {

                error.value =
                    'No fue posible consultar las ONU desde ACS Control.'

                console.error(e)

            } finally {

                loading.value = false
            }
        }


        async function refreshAll() {

            if (refreshing.value)
                return

            refreshing.value = true

            try {

                /*
                 * Forzamos nueva consulta.
                 * No dependemos del estado anterior
                 * del array ni del cache del navegador.
                 */

                const response = await fetch(
                    `/api/devices?limit=2000&_=${Date.now()}`,
                    {
                        cache: 'no-store'
                    }
                )

                if (!response.ok) {
                    throw new Error(
                        `Devices HTTP ${response.status}`
                    )
                }

                const data =
                    await response.json()

                devices.value =
                    data.devices || []

                /*
                 * Actualizamos también el estado
                 * general del backend/GenieACS.
                 */

                await loadHealth()

                /*
                 * Si hay una ONU abierta,
                 * actualizamos su resumen.
                 */

                if (selectedDevice.value) {

                    const current =
                        devices.value.find(
                            d =>
                                d.id
                                === selectedDevice.value.id
                        )

                    if (current) {

                        selectedDevice.value = {
                            ...selectedDevice.value,
                            ...current
                        }
                    }
                }

                lastUpdated.value =
                    new Date()

            } catch (e) {

                console.error(e)

                alert(
                    'No fue posible actualizar ' +
                    'el estado de los equipos.'
                )

            } finally {

                refreshing.value = false
            }
        }


        async function openDevice(device) {

            stopRefresh()
            dataStatus.value = null
            certification.value = null
            detailLoading.value = true
            activeTab.value = 'resumen'

            selectedDevice.value = {
                ...device
            }

            try {

                const id = encodeURIComponent(device.id)

                const response = await fetch(
                    `/api/devices/${id}`,
                    {
                        cache: 'no-store'
                    }
                )

                if (response.ok) {

                    const data = await response.json()

                    selectedDevice.value =
                        data.device || device

                    dataStatus.value = data.data_status || null
                    certification.value = data.certification || null
                }

            } catch (e) {
                console.error(e)
            }

            detailLoading.value = false

            // Si faltan datos o están viejos, se piden a la ONU sin bloquear la vista
            const ds = dataStatus.value
            if (ds && (!ds.complete || ds.stale))
                startRefresh()
        }


        const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

        const BRANCH_LABELS = {
            DeviceInfo: 'información del equipo',
            WANDevice: 'WAN',
            LANDevice: 'red local, Wi-Fi y hosts',
            WLANConfiguration: 'Wi-Fi',
            Hosts: 'hosts',
            X_HW_Security: 'seguridad',
            X_CATV_RFDevice: 'CATV',
            WiFi: 'Wi-Fi',
            IP: 'IP',
            PPP: 'PPPoE'
        }

        function branchLabel(path) {
            const parts = String(path || '').split('.')
            for (let i = parts.length - 1; i >= 0; i--) {
                if (BRANCH_LABELS[parts[i]])
                    return BRANCH_LABELS[parts[i]]
            }
            return parts[parts.length - 1] || path
        }

        function stopRefresh() {
            refreshToken++
            refreshState.value = ''
            refreshMessage.value = ''
            refreshNewData.value = false
        }

        async function refreshCall(id, method, force = false) {
            const r = await fetch(
                `/api/devices/${id}/refresh${force ? '?force=true' : ''}`,
                { method, cache: 'no-store' }
            )
            const data = await r.json().catch(() => ({}))
            if (!r.ok)
                throw new Error(data.detail || `HTTP ${r.status}`)
            return data
        }

        const TAB_LOADERS = () => ({
            internet: openWan,
            wifi: openWifi,
            catv: openCatv,
            seguridad: openSecurity
        })

        async function reloadActiveTab() {
            refreshNewData.value = false
            const loader = TAB_LOADERS()[activeTab.value]
            if (loader)
                await loader()
            if (refreshState.value === 'done')
                refreshState.value = ''
        }

        async function applyRefreshedData(deviceId, wasIncomplete) {
            const id = encodeURIComponent(deviceId)
            const r = await fetch(`/api/devices/${id}`, { cache: 'no-store' })

            if (!r.ok || !selectedDevice.value || selectedDevice.value.id !== deviceId)
                return

            const data = await r.json()
            selectedDevice.value = data.device || selectedDevice.value
            dataStatus.value = data.data_status || null
            certification.value = data.certification || null

            // La pestaña abierta se recarga sola si antes no tenía datos y no hay
            // un formulario en uso; si no, se ofrece recargarla para no borrar
            // lo que el técnico esté escribiendo.
            if (!TAB_LOADERS()[activeTab.value])
                return

            if (wasIncomplete && !wanFormOpen.value)
                await TAB_LOADERS()[activeTab.value]()
            else
                refreshNewData.value = true
        }

        async function startRefresh(force = false) {

            if (!selectedDevice.value)
                return

            const token = ++refreshToken
            const deviceId = selectedDevice.value.id
            const id = encodeURIComponent(deviceId)
            const wasIncomplete = !!dataStatus.value && !dataStatus.value.complete
            const alive = () =>
                token === refreshToken
                && selectedDevice.value
                && selectedDevice.value.id === deviceId

            refreshState.value = wasIncomplete ? 'reading' : 'updating'
            refreshMessage.value = ''
            refreshNewData.value = false

            let failed = []
            let changed = false

            try {
                // Varias rondas: la primera lectura de una ONU nueva descubre
                // ramas (p. ej. seguridad) que se piden en la siguiente.
                for (let round = 0; round < 3; round++) {

                    const res = await refreshCall(id, 'POST', force && round === 0)
                    if (!alive()) return

                    if (res.status === 'fresh')
                        break

                    changed = true

                    if (res.status !== 'done') {
                        const started = Date.now()

                        while (true) {
                            const elapsed = Date.now() - started
                            await sleep(elapsed < 30000 ? 2000 : 15000)
                            if (!alive()) return

                            const st = await refreshCall(id, 'GET')
                            if (!alive()) return

                            failed = failed.concat(st.failed || [])

                            if (!st.pending)
                                break

                            if (Date.now() - started >= 30000)
                                refreshState.value = 'waiting'

                            if (Date.now() - started >= 6 * 60000) {
                                refreshMessage.value =
                                    'La ONU no respondió. Las lecturas quedan en cola ' +
                                    'y se harán en su próximo reporte.'
                                return
                            }
                        }
                    }

                    if (failed.length)
                        break
                }

                if (changed)
                    await applyRefreshedData(deviceId, wasIncomplete)

                if (!alive()) return

                if (failed.length) {
                    refreshState.value = 'error'
                    refreshMessage.value =
                        'La ONU cortó la lectura de ' +
                        [...new Set(failed.map(f => branchLabel(f.branch)))].join(', ') +
                        '. El próximo intento se hará por partes más pequeñas.'
                    return
                }

                refreshState.value = changed ? 'done' : ''

                setTimeout(() => {
                    if (alive() && refreshState.value === 'done' && !refreshNewData.value)
                        refreshState.value = ''
                }, 4000)

            } catch (e) {
                if (!alive()) return
                console.error(e)
                refreshState.value = 'error'
                refreshMessage.value = e.message || 'No fue posible leer los datos de la ONU.'
            }
        }

        // Al cambiar de pestaña se cargan datos frescos: ya no hace falta el aviso
        watch(activeTab, () => {
            refreshNewData.value = false
            if (refreshState.value === 'done')
                refreshState.value = ''
        })


        
        async function addTag() {
            const tag = newTag.value.trim()

            if (!tag || !selectedDevice.value)
                return

            tagBusy.value = true

            try {
                const id = encodeURIComponent(selectedDevice.value.id)
                const t = encodeURIComponent(tag)

                const r = await fetch(
                    `/api/devices/${id}/tags/${t}`,
                    { method: 'POST' }
                )

                if (!r.ok)
                    throw new Error(`HTTP ${r.status}`)

                const data = await r.json()

                selectedDevice.value.tags = data.tags || []
                newTag.value = ''

                await loadDevices(false)

            } catch (e) {
                console.error(e)
                alert('No fue posible agregar la etiqueta.')
            } finally {
                tagBusy.value = false
            }
        }


        async function removeTag(tag) {
            if (!selectedDevice.value)
                return

            if (!confirm(`¿Eliminar etiqueta "${tag}"?`))
                return

            tagBusy.value = true

            try {
                const id = encodeURIComponent(selectedDevice.value.id)
                const t = encodeURIComponent(tag)

                const r = await fetch(
                    `/api/devices/${id}/tags/${t}`,
                    { method: 'DELETE' }
                )

                if (!r.ok)
                    throw new Error(`HTTP ${r.status}`)

                const data = await r.json()

                selectedDevice.value.tags = data.tags || []

                await loadDevices(false)

            } catch (e) {
                console.error(e)
                alert('No fue posible eliminar la etiqueta.')
            } finally {
                tagBusy.value = false
            }
        }


// Esc cierra el detalle de la ONU (salvo que haya un formulario abierto)
function onDetailKeydown(event) {

    if (
        event.key === 'Escape'
        && selectedDevice.value
        && !wanFormOpen.value
        && !configOpen.value
    ) {
        closeDevice()
    }
}

onMounted(() => window.addEventListener('keydown', onDetailKeydown))
onUnmounted(() => window.removeEventListener('keydown', onDetailKeydown))

function closeDevice() {
            stopRefresh()
            selectedDevice.value = null
        }

        
        async function openCatv() {
            activeTab.value = 'catv'
            catvLoading.value = true
            catvError.value = null

            try {
                const id = encodeURIComponent(selectedDevice.value.id)

                const r = await fetch(
                    `/api/devices/${id}/catv`,
                    { cache: 'no-store' }
                )

                if (!r.ok)
                    throw new Error(`HTTP ${r.status}`)

                const data = await r.json()
                catv.value = data.catv

            } catch (e) {
                console.error(e)
                catvError.value = 'No fue posible leer CATV.'
            } finally {
                catvLoading.value = false
            }
        }

        
        async function setCatv(action) {

            if (!selectedDevice.value || catvBusy.value)
                return

            const text =
                action === 'on'
                    ? 'ACTIVAR'
                    : 'DESACTIVAR'

            if (!confirm(`${text} CATV en esta ONU?`))
                return

            catvBusy.value = true

            try {
                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const r = await fetch(
                    `/api/devices/${id}/catv/${action}`,
                    { method: 'POST' }
                )

                if (!r.ok)
                    throw new Error(`HTTP ${r.status}`)

                await new Promise(
                    resolve => setTimeout(resolve, 2500)
                )

                await openCatv()

            } catch (e) {
                console.error(e)
                alert('No fue posible cambiar CATV.')
            } finally {
                catvBusy.value = false
            }
        }


function catvState(value) {
            if (
                value === 1 ||
                value === "1" ||
                value === true
            ) return "ACTIVO"

            if (
                value === 0 ||
                value === "0" ||
                value === false
            ) return "APAGADO"

            return "DESCONOCIDO"
        }


        

        async function openWanEdit(connection) {

            if (connection.protected) {
                alert('La WAN TR069 está protegida.')
                return
            }


            let type = 'dhcp'

            if (
                connection.object_type
                === 'WANPPPConnection'
            ) {
                type = 'pppoe'
            }
            else if (
                String(
                    connection.addressing_type || ''
                ).toLowerCase() === 'static'
            ) {
                type = 'static'
            }

            wanEditing.value = {
                wcd: connection.wan_connection_device,
                instance: connection.instance,
                object_type: connection.object_type
            }

            const id = encodeURIComponent(
                selectedDevice.value.id
            )

            const r = await fetch(
                `/api/devices/${id}/interfaces`,
                { cache: 'no-store' }
            )

            if (!r.ok) {
                alert(
                    'No fue posible obtener las interfaces.'
                )
                return
            }

            const data = await r.json()

            wanInterfaces.value =
                data.interfaces || []

            wanForm.value = {
                type: type,

                vlan:
                    connection.vlan ?? 1,

                priority:
                    connection.priority_8021p ?? 0,

                username:
                    connection.username || '',

                password: '',

                ip:
                    connection.ip || '',

                subnet_mask:
                    connection.subnet_mask || '',

                gateway:
                    connection.gateway || '',

                dns:
                    connection.dns || '',

                nat:
                    connection.nat === true,

                mtu:
                    connection.mtu ||
                    (
                        type === 'pppoe'
                            ? 1492
                            : 1500
                    ),

                bindings:
                    connection.lan_binding
                        ? connection.lan_binding
                            .split(',')
                            .filter(Boolean)
                        : []
            }

            wanMessage.value = ''
            wanFormOpen.value = true
        }


        async function openWanForm() {
            wanEditing.value = null
            wanMessage.value = ''
            wanForm.value = {
                type: 'pppoe',
                vlan: 110,
                priority: 0,

                username: '',
                password: '',

                ip: '',
                subnet_mask: '',
                gateway: '',
                dns: '',

                nat: true,
                mtu: 1492,
                bindings: []
            }

            const id = encodeURIComponent(selectedDevice.value.id)

            const r = await fetch(
                `/api/devices/${id}/interfaces`,
                { cache: 'no-store' }
            )

            if (!r.ok) {
                alert('No fue posible obtener las interfaces.')
                return
            }

            const data = await r.json()
            wanInterfaces.value = data.interfaces || []
            wanFormOpen.value = true
        }

        function closeWanForm() {
            if (!wanCreating.value)
                wanFormOpen.value = false
        }

        function toggleBinding(path) {
            const list = wanForm.value.bindings

            if (list.includes(path))
                wanForm.value.bindings =
                    list.filter(x => x !== path)
            else
                wanForm.value.bindings.push(path)
        }


        function setWanType(type) {

            wanForm.value.type = type

            if (type === 'pppoe') {
                wanForm.value.mtu = 1492

                wanForm.value.ip = ''
                wanForm.value.subnet_mask = ''
                wanForm.value.gateway = ''
                wanForm.value.dns = ''
            }

            if (type === 'dhcp') {
                wanForm.value.mtu = 1500

                wanForm.value.username = ''
                wanForm.value.password = ''

                wanForm.value.ip = ''
                wanForm.value.subnet_mask = ''
                wanForm.value.gateway = ''
                wanForm.value.dns = ''
            }

            if (type === 'static') {
                wanForm.value.mtu = 1500

                wanForm.value.username = ''
                wanForm.value.password = ''
            }
        }


        async function createWan() {

            const type =
                wanForm.value.type || 'pppoe'

            if (
                !wanForm.value.vlan
                || wanForm.value.vlan < 1
                || wanForm.value.vlan > 4094
            ) {
                wanMessage.value = 'VLAN inválida.'
                return
            }

            if (
                type === 'pppoe'
                && (
                    !wanForm.value.username
                    || !wanForm.value.password
                )
            ) {
                wanMessage.value =
                    'Usuario y contraseña PPPoE son obligatorios.'
                return
            }

            if (
                type === 'static'
                && (
                    !wanForm.value.ip
                    || !wanForm.value.subnet_mask
                    || !wanForm.value.gateway
                    || !wanForm.value.dns
                )
            ) {
                wanMessage.value =
                    'IP, máscara, gateway y DNS son obligatorios.'
                return
            }

            wanCreating.value = true
            wanMessage.value = 'Creando WAN… algunas ONU tardan hasta 2 minutos en confirmar.'

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const manufacturer = String(
                    selectedDevice.value.manufacturer || ''
                ).toUpperCase()

                const isVsol =
                    manufacturer.includes('VSOL')

                let endpoint
                let payload = {
                    vlan: wanForm.value.vlan,
                    priority: wanForm.value.priority,
                    nat: wanForm.value.nat,
                    mtu: wanForm.value.mtu,
                    bindings: wanForm.value.bindings
                }

                // ---------------------------
                // PPPoE
                // ---------------------------

                if (type === 'pppoe') {

                    payload.username =
                        wanForm.value.username

                    payload.password =
                        wanForm.value.password

                    endpoint = isVsol
                        ? `/api/devices/${id}/wan/vsol/create-pppoe`
                        : `/api/devices/${id}/wan/create-pppoe`
                }

                // ---------------------------
                // DHCP
                // ---------------------------

                else if (type === 'dhcp') {

                    if (isVsol) {
                        endpoint =
                            `/api/devices/${id}/wan/vsol/create-ip`

                        payload.addressing_type = 'DHCP'
                    }
                    else {
                        endpoint =
                            `/api/devices/${id}/wan/create-dhcp`
                    }
                }

                // ---------------------------
                // STATIC
                // ---------------------------

                else if (type === 'static') {

                    // Fuera de VSOL, el backend valida si el modelo admite IP fija
                    endpoint = isVsol
                        ? `/api/devices/${id}/wan/vsol/create-ip`
                        : `/api/devices/${id}/wan/create-ip`

                    payload.addressing_type = 'STATIC'

                    payload.ip =
                        wanForm.value.ip

                    payload.subnet_mask =
                        wanForm.value.subnet_mask

                    payload.gateway =
                        wanForm.value.gateway

                    payload.dns =
                        wanForm.value.dns
                }

                else {
                    throw new Error(
                        'Tipo de WAN no soportado.'
                    )
                }

                const r = await fetch(
                    endpoint,
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type':
                                'application/json'
                        },
                        body: JSON.stringify(payload)
                    }
                )

                const data = await r.json()

                if (!r.ok) {
                    throw new Error(
                        data.detail || `HTTP ${r.status}`
                    )
                }

                wanMessage.value =
                    `WAN creada: ${data.status}`

                await new Promise(
                    resolve => setTimeout(resolve, 1500)
                )

                wanFormOpen.value = false

                await openWan()

            } catch (e) {

                wanMessage.value =
                    `Error: ${e.message}`

            } finally {

                wanCreating.value = false
            }
        }


        async function deleteWan(connection) {

            if (connection.protected) {
                alert('La WAN TR069 está protegida.')
                return
            }

            const confirmation = prompt(
                `Vas a eliminar permanentemente la WAN ${connection.wan_connection_device}.\n\n` +
                `VLAN: ${connection.vlan ?? '-'}\n` +
                `Servicio: ${(connection.services || []).join(' + ')}\n\n` +
                `Escribe ELIMINAR para continuar:`
            )

            if (confirmation !== 'ELIMINAR') {
                return
            }

            wanDeleteBusy.value = connection.wan_connection_device

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const r = await fetch(
                    `/api/devices/${id}/wan/` +
                    `${connection.wan_connection_device}/` +
                    `${connection.object_type}/` +
                    `${connection.instance}`,
                    {
                        method: 'DELETE'
                    }
                )

                const data = await r.json()

                if (!r.ok) {
                    throw new Error(
                        data.detail ||
                        `HTTP ${r.status}`
                    )
                }

                if (
                    data.status !== 'CONFIRMADO'
                    && data.status !== 'PENDIENTE'
                ) {
                    alert(
                        `Resultado: ${data.status}`
                    )
                }

                const deleted =
                    await waitWanDeleted(connection)

                if (!deleted) {
                    alert(
                        'La eliminación fue enviada, pero GenieACS aún no actualiza el inventario.'
                    )
                }

            } catch (e) {

                alert(
                    `No fue posible eliminar la WAN: ${e.message}`
                )

            } finally {

                wanDeleteBusy.value = null
            }
        }

        async function editWan() {

            if (!wanEditing.value)
                return

            const type =
                wanForm.value.type

            if (!wanForm.value.vlan) {
                wanMessage.value =
                    'VLAN obligatoria.'
                return
            }

            if (
                type === 'pppoe'
                && !wanForm.value.username
            ) {
                wanMessage.value =
                    'Usuario PPPoE obligatorio.'
                return
            }

            if (
                type === 'static'
                && (
                    !wanForm.value.ip
                    || !wanForm.value.subnet_mask
                    || !wanForm.value.gateway
                    || !wanForm.value.dns
                )
            ) {
                wanMessage.value =
                    'Completa IP, máscara, gateway y DNS.'
                return
            }

            wanCreating.value = true
            wanMessage.value = ''

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const payload = {
                    vlan:
                        wanForm.value.vlan,

                    priority:
                        wanForm.value.priority,

                    nat:
                        wanForm.value.nat,

                    mtu:
                        wanForm.value.mtu,

                    bindings:
                        wanForm.value.bindings
                }

                let endpoint

                if (
                    wanEditing.value.object_type
                    === 'WANPPPConnection'
                ) {

                    payload.username =
                        wanForm.value.username

                    if (wanForm.value.password) {
                        payload.password =
                            wanForm.value.password
                    }

                    endpoint =
                        `/api/devices/${id}/wan/` +
                        `${wanEditing.value.wcd}/pppoe/` +
                        `${wanEditing.value.instance}`
                }

                else {

                    if (type === 'static') {

                        payload.ip =
                            wanForm.value.ip

                        payload.subnet_mask =
                            wanForm.value.subnet_mask

                        payload.gateway =
                            wanForm.value.gateway

                        payload.dns =
                            wanForm.value.dns
                    }

                    endpoint =
                        `/api/devices/${id}/wan/` +
                        `${wanEditing.value.wcd}/ip/` +
                        `${wanEditing.value.instance}`
                }

                const r = await fetch(
                    endpoint,
                    {
                        method: 'PATCH',
                        headers: {
                            'Content-Type':
                                'application/json'
                        },
                        body:
                            JSON.stringify(payload)
                    }
                )

                const data = await r.json()

                if (!r.ok) {
                    throw new Error(
                        data.detail ||
                        `HTTP ${r.status}`
                    )
                }

                wanMessage.value =
                    `Cambios aplicados: ${data.status}`

                await new Promise(
                    resolve =>
                        setTimeout(resolve, 1200)
                )

                wanFormOpen.value = false
                wanEditing.value = null

                await openWan()

            } catch (e) {

                wanMessage.value =
                    `Error: ${e.message}`

            } finally {

                wanCreating.value = false
            }
        }


        async function toggleWan(connection) {

            if (connection.protected) {
                alert(
                    'Esta WAN contiene TR069 y está protegida.'
                )
                return
            }

            const action =
                connection.enabled
                    ? 'disable'
                    : 'enable'

            const verb =
                connection.enabled
                    ? 'desactivar'
                    : 'activar'

            if (!confirm(
                `¿Deseas ${verb} la WAN ` +
                `${connection.wan_connection_device}?`
            )) {
                return
            }

            wanToggleBusy.value =
                connection.wan_connection_device

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const kind =
                    connection.object_type
                    === 'WANPPPConnection'
                        ? 'pppoe'
                        : 'ip'

                const r = await fetch(
                    `/api/devices/${id}/wan/` +
                    `${connection.wan_connection_device}/` +
                    `${kind}/` +
                    `${connection.instance}/${action}`,
                    {
                        method: 'POST'
                    }
                )

                const data = await r.json()

                if (!r.ok) {
                    throw new Error(
                        data.detail ||
                        `HTTP ${r.status}`
                    )
                }

                await openWan()

            } catch (e) {

                alert(
                    `No fue posible ${verb} la WAN: ` +
                    e.message
                )

            } finally {

                wanToggleBusy.value = null
            }
        }


        async function openWan() {
            activeTab.value = 'internet'
            wanLoading.value = true
            wanError.value = null

            try {
                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const r = await fetch(
                    `/api/devices/${id}/wan`,
                    { cache: 'no-store' }
                )

                if (!r.ok)
                    throw new Error(`HTTP ${r.status}`)

                wan.value = await r.json()

            } catch (e) {
                console.error(e)
                wanError.value =
                    'No fue posible leer las conexiones WAN.'
            } finally {
                wanLoading.value = false
            }
        }

        async function waitWanDeleted(connection) {

            const id = encodeURIComponent(
                selectedDevice.value.id
            )

            for (let attempt = 0; attempt < 6; attempt++) {

                const r = await fetch(
                    `/api/devices/${id}/wan`,
                    { cache: 'no-store' }
                )

                if (r.ok) {

                    const data = await r.json()

                    wan.value = data

                    const exists = (
                        data.wan || []
                    ).some(
                        item =>
                            item.wan_connection_device
                                === connection.wan_connection_device
                            &&
                            item.object_type
                                === connection.object_type
                            &&
                            item.instance
                                === connection.instance
                    )

                    if (!exists)
                        return true
                }

                await new Promise(
                    resolve => setTimeout(resolve, 2000)
                )
            }

            return false
        }


        function serviceText(services) {
            if (!services || !services.length)
                return '-'

            return services.join(' + ')
        }

        function bindingText(value) {
            if (!value)
                return 'Sin interfaces asociadas'

            return value
                .split(',')
                .map(x => {
                    const eth = x.match(
                        /LANEthernetInterfaceConfig\.(\d+)/
                    )

                    if (eth)
                        return `LAN ${eth[1]}`

                    const wlan = x.match(
                        /WLANConfiguration\.(\d+)/
                    )

                    if (wlan)
                        return `WLAN ${wlan[1]}`

                    return x
                })
                .join(', ')
        }



        // ACS_WIFI_EDITOR_15B2A

        const wifiForms = ref({})
        const wifiBusy = ref(null)
        const wifiMessage = ref({})


        function wifiBool(value) {

            return (
                value === true
                || value === 1
                || value === '1'
                || String(value).toLowerCase()
                    === 'true'
            )
        }


        function wifiChannels(index) {

            const form =
                wifiForms.value[index]

            if (!form)
                return []

            if (form.band === '2.4 GHz') {
                return [
                    1, 2, 3, 4, 5, 6,
                    7, 8, 9, 10, 11
                ]
            }

            if (form.band === '5 GHz') {
                return [
                    36, 40, 44, 48,
                    52, 56, 60, 64,
                    100, 104, 108, 112,
                    116,
                    136, 140,
                    149, 153, 157, 161
                ]
            }

            return []
        }


        async function openWifi() {

            activeTab.value = 'wifi'
            wifiLoading.value = true
            wifiError.value = null

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const r = await fetch(
                    `/api/devices/${id}/wifi`,
                    {
                        cache: 'no-store'
                    }
                )

                if (!r.ok) {
                    throw new Error(
                        `HTTP ${r.status}`
                    )
                }

                const data = await r.json()

                wifi.value = data.wifi

                const raw = data.wifi || {}
                const forms = {}

                const radios = Object
                    .values(raw)
                    .filter(
                        radio =>
                            radio
                            && radio.supported
                            && radio.index !== null
                            && radio.index !== undefined
                    )
                    .map(
                        radio => ({
                            index: Number(radio.index),
                            band: radio.band,
                            data: radio
                        })
                    )

                for (const radio of radios) {

                    const band = radio.data

                    if (!band)
                        continue

                    let channel = Number(
                        band.channel || 0
                    )

                    if (
                        channel === 0
                        && band.current_channel
                    ) {
                        channel = Number(
                            band.current_channel
                        )
                    }

                    forms[radio.index] = {

                        index:
                            radio.index,

                        band:
                            radio.band,

                        enabled:
                            wifiBool(
                                band.enabled
                            ),

                        ssid:
                            band.ssid || '',

                        password: '',

                        auto_channel:
                            wifiBool(
                                band.auto_channel
                            ),

                        channel:
                            channel || 0,

                        current_channel:
                            band.current_channel
                            || '',

                        hidden:
                            wifiBool(
                                band.hidden
                            ),

                        standard:
                            band.standard
                            || '',

                        encryption:
                            band.encryption
                            || ''
                    }
                }

                wifiForms.value = forms

            } catch (e) {

                console.error(e)

                wifiError.value =
                    'No fue posible leer el Wi-Fi.'

            } finally {

                wifiLoading.value = false
            }
        }


        async function saveWifi(index) {

            const form =
                wifiForms.value[index]

            if (!form)
                return

            wifiMessage.value[index] = ''

            if (!form.ssid.trim()) {

                wifiMessage.value[index] =
                    'El SSID es obligatorio.'

                return
            }

            if (
                form.password
                && (
                    form.password.length < 8
                    || form.password.length > 63
                )
            ) {

                wifiMessage.value[index] =
                    'La contraseña debe tener entre 8 y 63 caracteres.'

                return
            }

            if (
                !form.auto_channel
                && !Number(form.channel)
            ) {

                wifiMessage.value[index] =
                    'Selecciona un canal manual.'

                return
            }

            wifiBusy.value = index

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const payload = {

                    enabled:
                        form.enabled,

                    ssid:
                        form.ssid.trim(),

                    auto_channel:
                        form.auto_channel,

                    hidden:
                        form.hidden
                }

                if (!form.auto_channel) {

                    payload.channel =
                        Number(form.channel)
                }

                // Clave vacía = conservar actual.
                if (form.password) {

                    payload.password =
                        form.password
                }

                const r = await fetch(
                    `/api/devices/${id}/wifi/${index}`,
                    {
                        method: 'PATCH',

                        headers: {
                            'Content-Type':
                                'application/json'
                        },

                        body:
                            JSON.stringify(payload)
                    }
                )

                const data = await r.json()

                if (!r.ok) {

                    throw new Error(
                        data.detail
                        || `HTTP ${r.status}`
                    )
                }

                const status =
                    data.status || 'ENVIADO'

                await openWifi()

                wifiMessage.value[index] =
                    status === 'CONFIRMADO'
                        ? '✓ Cambios confirmados'
                        : `Cambios enviados: ${status}`

            } catch (e) {

                wifiMessage.value[index] =
                    `Error: ${e.message}`

            } finally {

                wifiBusy.value = null
            }
        }


        function channelText(band) {
            if (band.auto_channel) {
                return band.current_channel
                    ? `Automático (actual ${band.current_channel})`
                    : 'Automático'
            }

            return band.channel || band.current_channel || '-'
        }


        // ====================================================
        // Formato
        // ====================================================

        
        // ACS_SECURITY_UI_16B2_FIX

        const securityData = ref(null)
        const securityLoading = ref(false)
        const securityError = ref(null)
        const securityBusy = ref(null)
        const securityMessage = ref('')


        async function openSecurity() {

            activeTab.value = 'seguridad'
            securityLoading.value = true
            securityError.value = null

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const r = await fetch(
                    `/api/devices/${id}/security-module`,
                    {
                        cache: 'no-store'
                    }
                )

                const data = await r.json()

                if (!r.ok) {
                    throw new Error(
                        data.detail ||
                        `HTTP ${r.status}`
                    )
                }

                securityData.value = data

            } catch (e) {

                securityError.value =
                    `No fue posible leer Seguridad: ${e.message}`

            } finally {

                securityLoading.value = false
            }
        }


        async function setFirewallGrade(grade) {

            if (
                grade === securityData.value.firewall_grade
            ) {
                return
            }

            let text

            if (grade === 0) {

                text =
                    '¿Cambiar el firewall a nivel BAJO? ' +
                    'Se permitirá habilitar servicios desde WAN.'

            } else {

                text =
                    '¿Cambiar el firewall a nivel ALTO? ' +
                    'No podrán realizarse nuevas activaciones WAN. ' +
                    'Los servicios que ya estén activos no se apagarán automáticamente.'
            }

            if (!confirm(text))
                return

            securityBusy.value = 'firewall'
            securityMessage.value = ''

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const r = await fetch(
                    `/api/devices/${id}/security-module/firewall`,
                    {
                        method: 'PATCH',
                        headers: {
                            'Content-Type':
                                'application/json'
                        },
                        body: JSON.stringify({
                            grade: grade
                        })
                    }
                )

                const data = await r.json()

                if (!r.ok) {
                    throw new Error(
                        data.detail ||
                        `HTTP ${r.status}`
                    )
                }

                await openSecurity()

                securityMessage.value =
                    `Firewall: ${data.status}`

            } catch (e) {

                securityMessage.value =
                    `Error: ${e.message}`

            } finally {

                securityBusy.value = null
            }
        }


        async function changeSecurityService(
            service,
            payload
        ) {

            securityBusy.value = service.id
            securityMessage.value = ''

            try {

                const id = encodeURIComponent(
                    selectedDevice.value.id
                )

                const r = await fetch(
                    `/api/devices/${id}/security-module/service/${service.id}`,
                    {
                        method: 'PATCH',

                        headers: {
                            'Content-Type':
                                'application/json'
                        },

                        body:
                            JSON.stringify(payload)
                    }
                )

                const data = await r.json()

                if (!r.ok) {
                    throw new Error(
                        data.detail ||
                        `HTTP ${r.status}`
                    )
                }

                await openSecurity()

                securityMessage.value =
                    `${service.label}: ${data.status}`

            } catch (e) {

                securityMessage.value =
                    `Error: ${e.message}`

            } finally {

                securityBusy.value = null
            }
        }


        async function toggleSecurityWan(service) {

            const desired =
                !service.wan_enabled

            /*
             * REGLA:
             *
             * Firewall Bajo = puede activar.
             * Firewall Alto = NO puede activar.
             *
             * Si ya estaba activo, siempre puede apagarlo.
             */

            if (
                desired &&
                securityData.value.firewall_grade !== 0
            ) {

                securityMessage.value =
                    '🛡 El firewall debe estar en nivel Bajo para activar servicios por WAN.'

                return
            }

            if (desired) {

                let message =
                    `¿Activar ${service.label} desde WAN?`

                if (
                    [
                        'http',
                        'telnet',
                        'ftp',
                        'tftp'
                    ].includes(service.id)
                ) {

                    message +=
                        '\n\nEste protocolo puede aumentar la exposición del equipo.'
                }

                if (!confirm(message))
                    return
            }

            await changeSecurityService(
                service,
                {
                    wan_enabled: desired
                }
            )
        }


        async function toggleSecurityLan(service) {

            await changeSecurityService(
                service,
                {
                    lan_enabled:
                        !service.lan_enabled
                }
            )
        }


        async function saveSecurityDetails(service) {

            const payload = {}

            if (
                service.port_supported &&
                service.port_writable &&
                service.wan_port
            ) {

                payload.wan_port =
                    Number(service.wan_port)
            }

            if (
                service.ip_supported &&
                service.ip_writable
            ) {

                payload.specific_ip =
                    service.specific_ip || ''
            }

            if (
                Object.keys(payload).length === 0
            ) {

                securityMessage.value =
                    'Este servicio no expone ajustes adicionales.'

                return
            }

            await changeSecurityService(
                service,
                payload
            )
        }


                async function openConfig() {

            configOpen.value = true
            configLoading.value = true
            configError.value = null

            try {

                const [cfgResponse] =
                    await Promise.all([
                        fetch(
                            '/api/system/config',
                            {
                                cache: 'no-store'
                            }
                        ),
                        loadHealth()
                    ])

                const cfg =
                    await cfgResponse.json()

                if (!cfgResponse.ok) {
                    throw new Error(
                        cfg.detail
                        || `HTTP ${cfgResponse.status}`
                    )
                }

                systemConfig.value = cfg

            } catch (e) {

                console.error(e)

                configError.value =
                    `No fue posible leer configuración: ${e.message}`

            } finally {

                configLoading.value = false
            }
        }


        function closeConfig() {
            configOpen.value = false
        }


        async function testGenieConnection() {

            configLoading.value = true
            configError.value = null

            try {

                await Promise.all([
                    loadHealth(),
                    loadDevices(false)
                ])

                if (!health.value.genieacs) {
                    throw new Error(
                        'GenieACS no respondió'
                    )
                }

                lastUpdated.value =
                    new Date()

            } catch (e) {

                configError.value =
                    `Prueba fallida: ${e.message}`

            } finally {

                configLoading.value = false
            }
        }


function formatDate(value) {

            if (!value) {
                return 'Sin información'
            }

            try {

                return new Intl.DateTimeFormat(
                    'es-CO',
                    {
                        timeZone: 'America/Bogota',
                        dateStyle: 'medium',
                        timeStyle: 'medium'
                    }
                ).format(new Date(value))

            } catch {
                return value
            }
        }


        function formatUptime(seconds) {

            if (
                seconds === null ||
                seconds === undefined
            ) {
                return 'Sin información'
            }

            const value = Number(seconds)

            if (Number.isNaN(value)) {
                return seconds
            }

            const days = Math.floor(value / 86400)

            const hours = Math.floor(
                (value % 86400) / 3600
            )

            const minutes = Math.floor(
                (value % 3600) / 60
            )

            if (days > 0) {
                return `${days} d ${hours} h`
            }

            if (hours > 0) {
                return `${hours} h ${minutes} min`
            }

            return `${minutes} min`
        }


        // ====================================================
        // SESION Y ROLES
        // ====================================================

        const currentUser = ref(null)
        const authChecked = ref(false)
        const loginForm = ref({ username: '', password: '' })
        const loginBusy = ref(false)
        const loginError = ref('')

        const isAdmin = computed(() =>
            currentUser.value?.role === 'admin'
        )

        function roleLabel(role) {
            return role === 'admin' ? 'Admin' : 'Técnico'
        }

        // Cualquier 401 de la API (sesion vencida o revocada) vuelve al login.
        const nativeFetch = window.fetch.bind(window)

        window.fetch = async (...args) => {
            const response = await nativeFetch(...args)
            const url = String(args[0]?.url || args[0] || '')

            if (
                response.status === 401
                && url.includes('/api/')
                && !url.includes('/api/auth/')
                && currentUser.value
            ) {
                stopApp()
                currentUser.value = null
                loginError.value = 'Tu sesión expiró. Inicia sesión de nuevo.'
            }

            return response
        }

        async function startApp() {

            await Promise.all([
                loadHealth(),
                loadDevices()
            ])

            if (!refreshTimer) {
                refreshTimer = setInterval(
                    refreshAll,
                    30000
                )
            }
        }

        function stopApp() {

            if (refreshTimer) {
                clearInterval(refreshTimer)
                refreshTimer = null
            }

            selectedDevice.value = null
            configOpen.value = false
            auditOpen.value = false
            usersOpen.value = false
            devices.value = []
        }

        async function login() {

            loginBusy.value = true
            loginError.value = ''

            try {
                const r = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(loginForm.value)
                })

                const data = await r.json().catch(() => ({}))

                if (!r.ok) {
                    loginError.value =
                        data.detail || 'No fue posible iniciar sesión'
                    return
                }

                currentUser.value = data.user
                loginForm.value.password = ''
                activeView.value = 'inicio'
                await startApp()

            } catch (e) {
                loginError.value = 'Sin conexión con el servidor'

            } finally {
                loginBusy.value = false
            }
        }

        async function logout() {

            try {
                await fetch('/api/auth/logout', { method: 'POST' })
            } catch (e) {
                // Aun sin conexion, se cierra la sesion local.
            }

            stopApp()
            currentUser.value = null
            loginError.value = ''
        }


        // ====================================================
        // STAFF: gestion de usuarios (solo admin)
        // ====================================================

        const usersOpen = ref(false)
        const users = ref([])
        const usersLoading = ref(false)
        const usersError = ref('')
        const userBusy = ref(false)

        const emptyUserForm = () => ({
            username: '',
            full_name: '',
            role: 'technical',
            password: ''
        })

        const userForm = ref(emptyUserForm())

        async function usersRequest(url, options = {}) {

            const r = await fetch(url, {
                headers: { 'Content-Type': 'application/json' },
                ...options
            })

            const data = await r.json().catch(() => ({}))

            if (!r.ok)
                throw new Error(data.detail || `HTTP ${r.status}`)

            return data
        }

        async function loadUsers() {

            usersLoading.value = true
            usersError.value = ''

            try {
                users.value = (await usersRequest('/api/users')).users

            } catch (e) {
                usersError.value = e.message

            } finally {
                usersLoading.value = false
            }
        }

        async function openUsers() {
            usersOpen.value = true
            userForm.value = emptyUserForm()
            await loadUsers()
        }

        function closeUsers() {
            usersOpen.value = false
        }

        async function createUser() {

            userBusy.value = true
            usersError.value = ''

            try {
                await usersRequest('/api/users', {
                    method: 'POST',
                    body: JSON.stringify(userForm.value)
                })

                userForm.value = emptyUserForm()
                await loadUsers()

            } catch (e) {
                usersError.value = e.message

            } finally {
                userBusy.value = false
            }
        }

        async function updateUser(user, changes, confirmText) {

            if (confirmText && !confirm(confirmText))
                return

            userBusy.value = true
            usersError.value = ''

            try {
                await usersRequest(`/api/users/${user.id}`, {
                    method: 'PATCH',
                    body: JSON.stringify(changes)
                })

                await loadUsers()

            } catch (e) {
                usersError.value = e.message

            } finally {
                userBusy.value = false
            }
        }

        async function deleteUser(user) {

            const typed = prompt(
                `Se eliminará el usuario ${user.username} y se cerrarán sus sesiones.\n` +
                `Su historial en la auditoría se conserva.\n\n` +
                `Escriba ${user.username} para confirmar:`
            )

            if (typed !== user.username)
                return

            userBusy.value = true
            usersError.value = ''

            try {
                await usersRequest(`/api/users/${user.id}`, { method: 'DELETE' })
                await loadUsers()

            } catch (e) {
                usersError.value = e.message

            } finally {
                userBusy.value = false
            }
        }

        async function resetUserPassword(user) {

            const password = prompt(
                `Nueva contraseña para ${user.username} (mínimo 10 caracteres):`
            )

            if (!password)
                return

            await updateUser(user, { password })
        }


        onMounted(async () => {

            try {
                const r = await fetch('/api/auth/me', { cache: 'no-store' })

                if (r.ok)
                    currentUser.value = (await r.json()).user

            } catch (e) {
                // Sin servidor: se muestra el login con el error al intentar.
            }

            authChecked.value = true

            if (currentUser.value)
                await startApp()
        })


        onUnmounted(() => {

            if (refreshTimer) {
                clearInterval(refreshTimer)
            }
        })


        return {
            currentUser,
            authChecked,
            loginForm,
            loginBusy,
            loginError,
            isAdmin,
            roleLabel,
            login,
            logout,
            usersOpen,
            users,
            usersLoading,
            usersError,
            userBusy,
            userForm,
            openUsers,
            closeUsers,
            createUser,
            updateUser,
            resetUserPassword,
            deleteUser,
            devices,
            loading,
            error,
            search,

            health,

            auditOpen,
            audits,
            auditLoading,
            openAudit,
            closeAudit,
            auditValue,
            auditFilter,
            AUDIT_FILTERS,
            auditLabel,
            auditResultClass,
            auditTargetType,
            setAuditFilter,

            selectedDevice,
            detailLoading,
            activeTab,

            newTag,
            tagBusy,
            addTag,
            removeTag,

            wan,
            wanLoading,
            wanError,
            wanFormOpen,
            wanEditing,
            wanInterfaces,
            wanCreating,
            wanMessage,
            wanForm,
            openWanForm,
            openWanEdit,
            editWan,
            closeWanForm,
            toggleBinding,
            setWanType,
            createWan,
            wanToggleBusy,
            wanDeleteBusy,
            toggleWan,
            deleteWan,
            openWan,
            serviceText,
            bindingText,

            wifi,
            wifiLoading,
            wifiError,
            openWifi,

            wifiForms,
            wifiBusy,
            wifiMessage,
            wifiChannels,
            saveWifi,

            catv,
            catvLoading,
            catvError,
            catvBusy,
            openCatv,
            setCatv,
            catvState,

            securityData,
            securityLoading,
            securityError,
            securityBusy,
            securityMessage,
            openSecurity,
            setFirewallGrade,
            toggleSecurityWan,
            toggleSecurityLan,
            saveSecurityDetails,
            channelText,

            total,
            online,
            offline,
            manufacturers,
            filteredDevices,

            activeView,
            openInventory,
            openInventoryFiltered,
            manufacturerBreakdown,
            manufacturerBreakdownOpen,

            inventoryStatus,
            inventoryManufacturer,
            inventoryModel,
            inventoryTag,
            inventoryAcs,

            manufacturerOptions,
            modelOptions,
            tagOptions,

            selectedInventoryIds,
            allVisibleSelected,

            deviceTags,
            deviceIp,
            deviceLastInform,
            relativeTime,

            clearInventoryFilters,
            isInventorySelected,
            toggleInventoryDevice,
            toggleAllVisible,
            clearInventorySelection,

            refreshing,
            lastUpdated,

            configOpen,
            configLoading,
            configError,
            systemConfig,
            openConfig,
            closeConfig,
            testGenieConnection,

            loadDevices,
            refreshAll,

            openDevice,
            closeDevice,
            dataStatus,
            certification,
            readOnly,
            refreshState,
            refreshMessage,
            refreshNewData,
            startRefresh,
            reloadActiveTab,

            formatDate,
            formatUptime
        }
    },


    template: `
        <div v-if="!authChecked" class="login-page">
            <div class="login-card login-loading">Cargando…</div>
        </div>

        <div v-else-if="!currentUser" class="login-page">

            <form class="login-card" @submit.prevent="login">

                <div class="login-brand">
                    <div class="brand-icon">A</div>
                    <div>
                        <strong>ACS Control</strong>
                        <small>Gestión de ONUs</small>
                    </div>
                </div>

                <label>
                    Usuario
                    <input
                        v-model="loginForm.username"
                        autocomplete="username"
                        autofocus
                        required
                    />
                </label>

                <label>
                    Contraseña
                    <input
                        v-model="loginForm.password"
                        type="password"
                        autocomplete="current-password"
                        required
                    />
                </label>

                <div v-if="loginError" class="login-error">
                    {{ loginError }}
                </div>

                <button
                    type="submit"
                    class="login-submit"
                    :disabled="loginBusy"
                >
                    {{ loginBusy ? 'Ingresando…' : 'Iniciar sesión' }}
                </button>

            </form>

        </div>

        <div v-else class="layout">

            <!-- ========================================= -->
            <!-- SIDEBAR                                   -->
            <!-- ========================================= -->

            <aside class="sidebar">

                <div class="brand">
                    <div class="brand-icon">
                        A
                    </div>

                    <div>
                        <div class="brand-name">
                            ACS Control
                        </div>

                        <div class="brand-subtitle">
                            Gestión TR-069
                        </div>
                    </div>
                </div>


                <nav class="nav">

                    <div class="nav-section">
                        GENERAL
                    </div>

                    <button
                        class="nav-item"
                        :class="{
                            active:
                                activeView === 'inicio'
                        }"
                        @click="
                            activeView = 'inicio'
                        "
                    >
                        <span class="nav-icon">⌂</span>
                        Inicio
                    </button>

                    <button
                        class="nav-item"
                        :class="{
                            active:
                                activeView
                                === 'dispositivos'
                        }"
                        @click="openInventory"
                    >
                        <span class="nav-icon">◉</span>
                        Dispositivos
                    </button>


                    <div class="nav-section">
                        OPERACIÓN
                    </div>

                    <button class="nav-item disabled">
                        <span class="nav-icon">▦</span>
                        Plantillas
                        <span class="soon">Pronto</span>
                    </button>

                    
                    <button
                        v-if="isAdmin"
                        class="nav-item"
                        @click="openAudit"
                    >
                        <span class="nav-icon">↺</span>
                        Auditoría
                    </button>



                    <template v-if="isAdmin">

                        <div class="nav-section">
                            SISTEMA
                        </div>

                        <button
                            class="nav-item"
                            @click="openUsers"
                        >
                            <span class="nav-icon">👤</span>
                            Staff
                        </button>

                        <button
                            class="nav-item"
                            @click="openConfig"
                        >
                            <span class="nav-icon">⚙</span>
                            Configuración
                        </button>

                    </template>

                </nav>


                <div class="sidebar-user">

                    <div class="sidebar-user-avatar">
                        {{ (currentUser.full_name || currentUser.username).charAt(0).toUpperCase() }}
                    </div>

                    <div class="sidebar-user-info">
                        <strong>{{ currentUser.full_name || currentUser.username }}</strong>
                        <small>{{ roleLabel(currentUser.role) }}</small>
                    </div>

                    <button
                        class="sidebar-logout"
                        title="Cerrar sesión"
                        @click="logout"
                    >
                        ⎋
                    </button>

                </div>


                <div class="sidebar-status">

                    <div
                        class="status-dot"
                        :class="{
                            online: health.healthy,
                            offline: !health.healthy
                        }"
                    ></div>

                    <div>
                        <div class="status-title">
                            {{ health.healthy
                                ? 'Sistema operativo'
                                : 'Sistema degradado'
                            }}
                        </div>

                        <div class="status-subtitle">
                            {{
                                health.genieacs
                                    ? 'GenieACS conectado'
                                    : 'GenieACS sin conexión'
                            }}
                        </div>
                    </div>

                </div>

            </aside>


            <!-- ========================================= -->
            <!-- PRINCIPAL                                  -->
            <!-- ========================================= -->

            <main class="main" :class="{ 'read-only': readOnly }">

                <header class="topbar">

                    <div>
                        <h1>
                            {{
                                activeView === 'inicio'
                                    ? 'Inicio'
                                    : 'Dispositivos'
                            }}
                        </h1>

                        <p>
                            {{
                                activeView === 'inicio'
                                    ? 'Resumen operativo de ACS Control'
                                    : 'Inventario y gestión centralizada de ONU'
                            }}
                        </p>
                    </div>


                    <div class="top-actions">

                        <div
                            class="connection-chip"
                            :class="health.genieacs ? 'ok' : 'fail'"
                        >
                            <span></span>

                            {{ health.genieacs
                                ? 'GenieACS conectado'
                                : 'GenieACS desconectado'
                            }}
                        </div>


                        <div
                            class="refresh-area"
                        >

                            <span
                                v-if="lastUpdated"
                                class="last-updated"
                            >
                                Actualizado
                                {{
                                    lastUpdated
                                    .toLocaleTimeString(
                                        'es-CO',
                                        {
                                            hour:
                                                '2-digit',
                                            minute:
                                                '2-digit',
                                            second:
                                                '2-digit'
                                        }
                                    )
                                }}
                            </span>

                            <button
                                class="refresh-button"
                                :disabled="refreshing"
                                @click="refreshAll"
                            >
                                {{
                                    refreshing
                                        ? '↻ Actualizando...'
                                        : '↻ Actualizar'
                                }}
                            </button>

                        </div>

                    </div>

                </header>


                <!-- ===================================== -->
                <!-- TARJETAS                              -->
                <!-- ===================================== -->

                <section
                    v-if="activeView === 'inicio'"
                    class="stats"
                >

                    <div
                        class="stat-card stat-card-action"
                        role="button"
                        tabindex="0"
                        title="Ver todas las ONUs"
                        @click="openInventoryFiltered()"
                        @keydown.enter="openInventoryFiltered()"
                        @keydown.space.prevent="openInventoryFiltered()"
                    >

                        <div class="stat-top">

                            <span>
                                Total ONU
                            </span>

                            <div class="stat-icon">
                                ◉
                            </div>

                        </div>

                        <strong>
                            {{ total }}
                        </strong>

                        <small>
                            Registradas en GenieACS
                        </small>

                    </div>


                    <div
                        class="stat-card stat-card-action"
                        role="button"
                        tabindex="0"
                        title="Ver ONUs en línea"
                        @click="openInventoryFiltered({ status: 'online' })"
                        @keydown.enter="openInventoryFiltered({ status: 'online' })"
                        @keydown.space.prevent="openInventoryFiltered({ status: 'online' })"
                    >

                        <div class="stat-top">

                            <span>
                                En línea
                            </span>

                            <div class="stat-icon green">
                                ✓
                            </div>

                        </div>

                        <strong>
                            {{ online }}
                        </strong>

                        <small>
                            Inform reciente
                        </small>

                    </div>


                    <div
                        class="stat-card stat-card-action"
                        role="button"
                        tabindex="0"
                        title="Ver ONUs fuera de línea"
                        @click="openInventoryFiltered({ status: 'offline' })"
                        @keydown.enter="openInventoryFiltered({ status: 'offline' })"
                        @keydown.space.prevent="openInventoryFiltered({ status: 'offline' })"
                    >

                        <div class="stat-top">

                            <span>
                                Fuera de línea
                            </span>

                            <div class="stat-icon red">
                                !
                            </div>

                        </div>

                        <strong>
                            {{ offline }}
                        </strong>

                        <small>
                            Sin Inform reciente
                        </small>

                    </div>


                    <div
                        class="stat-card stat-card-action"
                        :class="{ active: manufacturerBreakdownOpen }"
                        :aria-expanded="manufacturerBreakdownOpen"
                        role="button"
                        tabindex="0"
                        title="Ver ONUs por fabricante"
                        @click="manufacturerBreakdownOpen = !manufacturerBreakdownOpen"
                        @keydown.enter="manufacturerBreakdownOpen = !manufacturerBreakdownOpen"
                        @keydown.space.prevent="manufacturerBreakdownOpen = !manufacturerBreakdownOpen"
                    >

                        <div class="stat-top">

                            <span>
                                Fabricantes
                            </span>

                            <div class="stat-icon">
                                ◆
                            </div>

                        </div>

                        <strong>
                            {{ manufacturers }}
                        </strong>

                        <small>
                            Detectados automáticamente
                        </small>

                    </div>

                </section>


                <!-- ===================================== -->
                <!-- TABLA                                  -->
                <!-- ===================================== -->

                

                <!-- ===================================== -->
                <!-- INICIO / RESUMEN                      -->
                <!-- ===================================== -->

                <section
                    v-if="
                        activeView === 'inicio'
                        && manufacturerBreakdownOpen
                    "
                    class="manufacturer-breakdown"
                >

                    <div class="mb-head">

                        <div>
                            <strong>ONUs por fabricante</strong>
                            <small>
                                Haz clic en un fabricante para ver sus ONUs
                            </small>
                        </div>

                        <button
                            class="mb-close"
                            title="Cerrar"
                            @click="manufacturerBreakdownOpen = false"
                        >
                            ✕
                        </button>

                    </div>

                    <button
                        v-for="m in manufacturerBreakdown"
                        :key="m.name"
                        class="mb-row"
                        @click="openInventoryFiltered({ manufacturer: m.name })"
                    >

                        <span class="mb-name">{{ m.name }}</span>

                        <span class="mb-bar">
                            <span
                                class="mb-bar-online"
                                :style="{ width: (m.online / m.total * 100) + '%' }"
                            ></span>
                        </span>

                        <span class="mb-total">{{ m.total }}</span>
                        <span class="mb-online">{{ m.online }} en línea</span>
                        <span class="mb-offline">{{ m.offline }} fuera</span>

                    </button>

                </section>


                <section
                    v-if="activeView === 'inicio'"
                    class="home-overview"
                >

                    <div class="home-overview-main">

                        <div>
                            <small>
                                ESTADO GENERAL
                            </small>

                            <h2>
                                ACS Control operativo
                            </h2>

                            <p>
                                {{
                                    health.genieacs
                                        ? 'Conectado correctamente con GenieACS.'
                                        : 'Sin comunicación con GenieACS.'
                                }}
                            </p>
                        </div>


                        <div
                            class="home-system-state"
                            :class="
                                health.healthy
                                    ? 'ok'
                                    : 'fail'
                            "
                        >
                            {{
                                health.healthy
                                    ? '● Sistema operativo'
                                    : '● Sistema degradado'
                            }}
                        </div>

                    </div>


                    <div class="home-overview-grid">

                        <div>
                            <span>
                                Inventario
                            </span>

                            <strong>
                                {{ total }} ONU
                            </strong>
                        </div>


                        <div>
                            <span>
                                Disponibilidad
                            </span>

                            <strong>
                                {{ online }}
                                /
                                {{ total }}
                                online
                            </strong>
                        </div>


                        <div>
                            <span>
                                Última lectura
                            </span>

                            <strong>
                                {{
                                    lastUpdated
                                        ? lastUpdated
                                            .toLocaleTimeString(
                                                'es-CO'
                                            )
                                        : 'Inicial'
                                }}
                            </strong>
                        </div>


                        <div>
                            <span>
                                Origen
                            </span>

                            <strong>
                                GenieACS principal
                            </strong>
                        </div>

                    </div>


                    <button
                        class="home-inventory-button"
                        @click="openInventory"
                    >
                        Abrir inventario
                        →
                    </button>

                </section>



                <!-- ===================================== -->
                <!-- CENTRO DE DISPOSITIVOS                -->
                <!-- ===================================== -->

                <section
                    v-if="
                        activeView
                        === 'dispositivos'
                    "
                    class="device-panel inventory-panel"
                >

                    <div class="inventory-heading">

                        <div>
                            <h2>
                                Inventario de dispositivos
                            </h2>

                            <p>
                                {{
                                    filteredDevices.length
                                }}
                                de
                                {{ total }}
                                equipos
                            </p>
                        </div>


                        <div class="search-box">

                            <span>⌕</span>

                            <input
                                v-model="search"
                                type="search"
                                placeholder="Serial, modelo, IP, firmware, OUI o Tag..."
                            />

                        </div>

                    </div>


                    <!-- FILTROS -->

                    <div class="inventory-filters">

                        <label>
                            <span>
                                Estado
                            </span>

                            <select
                                v-model="
                                    inventoryStatus
                                "
                            >
                                <option value="all">
                                    Todos
                                </option>

                                <option value="online">
                                    Online
                                </option>

                                <option value="offline">
                                    Offline
                                </option>
                            </select>
                        </label>


                        <label>
                            <span>
                                Fabricante
                            </span>

                            <select
                                v-model="
                                    inventoryManufacturer
                                "
                            >
                                <option value="all">
                                    Todos
                                </option>

                                <option
                                    v-for="
                                        item
                                        in manufacturerOptions
                                    "
                                    :key="item"
                                    :value="item"
                                >
                                    {{ item }}
                                </option>
                            </select>
                        </label>


                        <label>
                            <span>
                                Modelo
                            </span>

                            <select
                                v-model="
                                    inventoryModel
                                "
                            >
                                <option value="all">
                                    Todos
                                </option>

                                <option
                                    v-for="
                                        item
                                        in modelOptions
                                    "
                                    :key="item"
                                    :value="item"
                                >
                                    {{ item }}
                                </option>
                            </select>
                        </label>


                        <label>
                            <span>
                                Tag
                            </span>

                            <select
                                v-model="
                                    inventoryTag
                                "
                            >
                                <option value="all">
                                    Todos
                                </option>

                                <option
                                    v-for="
                                        item
                                        in tagOptions
                                    "
                                    :key="item"
                                    :value="item"
                                >
                                    {{ item }}
                                </option>
                            </select>
                        </label>


                        <label>
                            <span>
                                GenieACS
                            </span>

                            <select
                                v-model="
                                    inventoryAcs
                                "
                            >
                                <option value="all">
                                    Todos
                                </option>

                                <option value="primary">
                                    Principal
                                </option>
                            </select>
                        </label>


                        <button
                            class="inventory-clear"
                            @click="
                                clearInventoryFilters
                            "
                        >
                            Limpiar
                        </button>

                    </div>


                    <!-- SELECCION -->

                    <div
                        v-if="
                            selectedInventoryIds.length
                        "
                        class="inventory-selection"
                    >

                        <strong>
                            {{
                                selectedInventoryIds.length
                            }}
                            seleccionado(s)
                        </strong>


                        <div>

                            <button
                                @click="
                                    clearInventorySelection
                                "
                            >
                                Limpiar selección
                            </button>


                            <button
                                disabled
                                title="
                                    Se habilitará al validar Plantillas
                                "
                            >
                                ▦ Aplicar plantilla
                            </button>

                        </div>

                    </div>


                    <!-- ESTADOS -->

                    <div
                        v-if="loading"
                        class="loading"
                    >
                        <div
                            class="spinner"
                        ></div>

                        Cargando dispositivos...
                    </div>


                    <div
                        v-else-if="error"
                        class="error-message"
                    >
                        {{ error }}
                    </div>


                    <div
                        v-else-if="
                            !filteredDevices.length
                        "
                        class="inventory-empty"
                    >
                        No existen dispositivos
                        con estos filtros.
                    </div>


                    <!-- TABLA -->

                    <div
                        v-else
                        class="inventory-table-wrap"
                    >

                        <table
                            class="inventory-table"
                        >

                            <thead>

                                <tr>

                                    <th
                                        class="
                                            inventory-check
                                        "
                                    >
                                        <input
                                            type="checkbox"
                                            :checked="
                                                allVisibleSelected
                                            "
                                            @change="
                                                toggleAllVisible
                                            "
                                        />
                                    </th>

                                    <th>Estado</th>

                                    <th>Serial</th>

                                    <th>
                                        Fabricante
                                    </th>

                                    <th>Modelo</th>

                                    <th>Firmware</th>

                                    <th>IP</th>

                                    <th>Tags</th>

                                    <th>
                                        Último Inform
                                    </th>

                                    <th>ACS</th>

                                </tr>

                            </thead>


                            <tbody>

                                <tr
                                    v-for="
                                        device
                                        in filteredDevices
                                    "
                                    :key="device.id"
                                    :class="{
                                        selected:
                                            isInventorySelected(
                                                device.id
                                            )
                                    }"
                                    @click="
                                        openDevice(device)
                                    "
                                >

                                    <td
                                        class="
                                            inventory-check
                                        "
                                        @click.stop
                                    >
                                        <input
                                            type="checkbox"
                                            :checked="
                                                isInventorySelected(
                                                    device.id
                                                )
                                            "
                                            @change="
                                                toggleInventoryDevice(
                                                    device.id
                                                )
                                            "
                                        />
                                    </td>


                                    <td>

                                        <span
                                            class="
                                                inventory-status
                                            "
                                            :class="
                                                device.online
                                                    ? 'online'
                                                    : 'offline'
                                            "
                                        >
                                            <i></i>

                                            {{
                                                device.online
                                                    ? 'Online'
                                                    : 'Offline'
                                            }}
                                        </span>

                                    </td>


                                    <td>

                                        <strong
                                            class="
                                                inventory-serial
                                            "
                                        >
                                            {{
                                                device.serial_number
                                                || device.id
                                            }}
                                        </strong>

                                        <small>
                                            {{
                                                device.oui
                                                || ''
                                            }}
                                        </small>

                                    </td>


                                    <td>
                                        {{
                                            device.manufacturer
                                            || '-'
                                        }}
                                    </td>


                                    <td>
                                        {{
                                            device.product_class
                                            || '-'
                                        }}
                                    </td>


                                    <td>
                                        {{
                                            device.software_version
                                            || '-'
                                        }}
                                    </td>


                                    <td
                                        class="
                                            inventory-ip
                                        "
                                    >
                                        {{
                                            deviceIp(device)
                                        }}
                                    </td>


                                    <td>

                                        <div
                                            v-if="
                                                deviceTags(
                                                    device
                                                ).length
                                            "
                                            class="
                                                inventory-tags
                                            "
                                        >

                                            <span
                                                v-for="
                                                    tag
                                                    in deviceTags(
                                                        device
                                                    )
                                                "
                                                :key="tag"
                                            >
                                                {{ tag }}
                                            </span>

                                        </div>

                                        <span v-else>
                                            -
                                        </span>

                                    </td>


                                    <td
                                        :title="
                                            formatDate(
                                                deviceLastInform(
                                                    device
                                                )
                                            )
                                        "
                                    >
                                        {{
                                            relativeTime(
                                                deviceLastInform(
                                                    device
                                                )
                                            )
                                        }}
                                    </td>


                                    <td>

                                        <span
                                            class="
                                                inventory-acs
                                            "
                                        >
                                            Principal
                                        </span>

                                    </td>

                                </tr>

                            </tbody>

                        </table>

                    </div>


                    <div
                        class="inventory-footer"
                    >
                        Mostrando
                        <strong>
                            {{ filteredDevices.length }}
                        </strong>
                        de
                        <strong>
                            {{ total }}
                        </strong>
                        dispositivos
                    </div>

                </section>



            </main>


            <!-- ========================================= -->
            
            <!-- AUDITORIA -->

            

            <!-- STAFF: gestion de usuarios (solo admin) -->

            <div
                v-if="usersOpen && isAdmin"
                class="config-overlay"
                @click.self="closeUsers"
            >

                <div class="config-modal users-modal">

                    <div class="config-modal-head">

                        <div>
                            <small>👤 SISTEMA</small>
                            <h2>Staff</h2>
                        </div>

                        <button class="config-close" @click="closeUsers">
                            ✕
                        </button>

                    </div>

                    <div v-if="usersError" class="users-error">
                        {{ usersError }}
                    </div>

                    <form class="users-form" @submit.prevent="createUser">

                        <strong>Nuevo usuario</strong>

                        <input v-model="userForm.username" placeholder="Usuario" required />
                        <input v-model="userForm.full_name" placeholder="Nombre (opcional)" />

                        <select v-model="userForm.role">
                            <option value="technical">Técnico</option>
                            <option value="admin">Admin</option>
                        </select>

                        <input
                            v-model="userForm.password"
                            type="password"
                            placeholder="Contraseña (mín. 10)"
                            autocomplete="new-password"
                            required
                        />

                        <button type="submit" :disabled="userBusy">
                            + Crear
                        </button>

                    </form>

                    <div v-if="usersLoading" class="users-empty">
                        Cargando usuarios…
                    </div>

                    <table v-else class="users-table">

                        <thead>
                            <tr>
                                <th>Usuario</th>
                                <th>Rol</th>
                                <th>Estado</th>
                                <th>Último ingreso</th>
                                <th></th>
                            </tr>
                        </thead>

                        <tbody>
                            <tr
                                v-for="u in users"
                                :key="u.id"
                                :class="{ inactive: !u.active }"
                            >
                                <td>
                                    <strong>{{ u.username }}</strong>
                                    <small v-if="u.full_name">{{ u.full_name }}</small>
                                </td>

                                <td>
                                    <select
                                        :value="u.role"
                                        :disabled="userBusy"
                                        @change="updateUser(u, { role: $event.target.value }, 'Cambiar el rol cierra las sesiones abiertas de ' + u.username + '. ¿Continuar?')"
                                    >
                                        <option value="technical">Técnico</option>
                                        <option value="admin">Admin</option>
                                    </select>
                                </td>

                                <td>
                                    <span :class="u.active ? 'text-green' : 'text-red'">
                                        {{ u.active ? 'Activo' : 'Inactivo' }}
                                    </span>
                                </td>

                                <td>
                                    {{ u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Nunca' }}
                                </td>

                                <td class="users-actions">
                                    <button
                                        :disabled="userBusy"
                                        @click="resetUserPassword(u)"
                                    >
                                        Contraseña
                                    </button>

                                    <button
                                        :disabled="userBusy || u.id === currentUser.id"
                                        @click="updateUser(u, { active: !u.active }, (u.active ? 'Desactivar' : 'Activar') + ' a ' + u.username + '?')"
                                    >
                                        {{ u.active ? 'Desactivar' : 'Activar' }}
                                    </button>

                                    <button
                                        class="users-delete"
                                        :disabled="userBusy || u.id === currentUser.id"
                                        :title="u.id === currentUser.id ? 'No puede eliminar su propio usuario' : 'Eliminar usuario'"
                                        @click="deleteUser(u)"
                                    >
                                        Eliminar
                                    </button>
                                </td>
                            </tr>
                        </tbody>

                    </table>

                </div>

            </div>


            <!-- CONFIGURACION 17A2 -->

            <div
                v-if="configOpen && isAdmin"
                class="config-overlay"
                @click.self="closeConfig"
            >

                <div
                    class="config-modal"
                >

                    <div
                        class="config-modal-head"
                    >

                        <div>

                            <small>
                                ⚙ SISTEMA
                            </small>

                            <h2>
                                Configuración
                            </h2>

                        </div>

                        <button
                            class="config-close"
                            @click="closeConfig"
                        >
                            ✕
                        </button>

                    </div>


                    <div
                        v-if="configLoading"
                        class="loading"
                    >
                        <div
                            class="spinner"
                        ></div>

                        Consultando sistema...
                    </div>


                    <div
                        v-else-if="configError"
                        class="error-message"
                    >
                        {{ configError }}
                    </div>


                    <template
                        v-else-if="systemConfig"
                    >

                        <div
                            class="config-section"
                        >

                            <div
                                class="config-title"
                            >
                                GenieACS
                            </div>


                            <div
                                class="config-grid"
                            >

                                <div
                                    class="config-box"
                                >
                                    <span>
                                        Estado
                                    </span>

                                    <strong
                                        :class="
                                            health.genieacs
                                                ? 'text-green'
                                                : 'text-red'
                                        "
                                    >
                                        {{
                                            health.genieacs
                                                ? '● Conectado'
                                                : '● Desconectado'
                                        }}
                                    </strong>
                                </div>


                                <div
                                    class="
                                        config-box
                                        config-wide
                                    "
                                >
                                    <span>
                                        NBI
                                    </span>

                                    <strong
                                        class="mono"
                                    >
                                        {{
                                            systemConfig
                                            .genieacs_nbi_url
                                        }}
                                    </strong>
                                </div>


                                <div
                                    class="config-box"
                                >
                                    <span>
                                        Equipos cargados
                                    </span>

                                    <strong>
                                        {{ devices.length }}
                                    </strong>
                                </div>

                            </div>


                            <button
                                class="
                                    config-test-button
                                "
                                :disabled="
                                    configLoading
                                "
                                @click="
                                    testGenieConnection
                                "
                            >
                                Probar conexión
                            </button>

                        </div>


                        <div
                            class="config-section"
                        >

                            <div
                                class="config-title"
                            >
                                ACS Control
                            </div>


                            <div
                                class="config-grid"
                            >

                                <div
                                    class="config-box"
                                >
                                    <span>
                                        API
                                    </span>

                                    <strong
                                        :class="
                                            health.api
                                                ? 'text-green'
                                                : 'text-red'
                                        "
                                    >
                                        {{
                                            health.api
                                                ? '● Operativa'
                                                : '● Error'
                                        }}
                                    </strong>
                                </div>


                                <div
                                    class="config-box"
                                >
                                    <span>
                                        PostgreSQL
                                    </span>

                                    <strong
                                        :class="
                                            health.postgresql
                                                ? 'text-green'
                                                : 'text-red'
                                        "
                                    >
                                        {{
                                            health.postgresql
                                                ? '● Operativo'
                                                : '● Error'
                                        }}
                                    </strong>
                                </div>


                                <div
                                    class="config-box"
                                >
                                    <span>
                                        Redis
                                    </span>

                                    <strong
                                        :class="
                                            health.redis
                                                ? 'text-green'
                                                : 'text-red'
                                        "
                                    >
                                        {{
                                            health.redis
                                                ? '● Operativo'
                                                : '● Error'
                                        }}
                                    </strong>
                                </div>


                                <div
                                    class="config-box"
                                >
                                    <span>
                                        GenieACS
                                    </span>

                                    <strong
                                        :class="
                                            health.genieacs
                                                ? 'text-green'
                                                : 'text-red'
                                        "
                                    >
                                        {{
                                            health.genieacs
                                                ? '● Operativo'
                                                : '● Error'
                                        }}
                                    </strong>
                                </div>

                            </div>

                        </div>


                        <div
                            class="
                                config-future
                            "
                        >
                            <strong>
                                Multi-GenieACS
                            </strong>

                            <span>
                                Esta sección quedará
                                preparada para agregar
                                más servidores GenieACS.
                            </span>
                        </div>

                    </template>

                </div>

            </div>


<div
                v-if="auditOpen && isAdmin"
                class="audit-overlay"
            >
                <section class="audit-panel">

                    <div class="audit-header">

                        <div>
                            <h2>Auditoría</h2>
                            <p>
                                Movimientos de los usuarios: sesiones,
                                gestión de usuarios y cambios en las ONUs
                            </p>

                            <div class="audit-filters">
                                <button
                                    v-for="f in AUDIT_FILTERS"
                                    :key="f.value"
                                    class="audit-filter"
                                    :class="{ active: auditFilter === f.value }"
                                    @click="setAuditFilter(f.value)"
                                >
                                    {{ f.label }}
                                </button>
                            </div>
                        </div>

                        <div class="audit-actions">

                            <button
                                class="refresh-button"
                                @click="openAudit"
                            >
                                ↻ Actualizar
                            </button>

                            <button
                                class="close-button"
                                @click="closeAudit"
                            >
                                ×
                            </button>

                        </div>

                    </div>

                    <div
                        v-if="auditLoading"
                        class="loading"
                    >
                        <div class="spinner"></div>
                        Consultando PostgreSQL...
                    </div>

                    <div
                        v-else
                        class="audit-table-wrap"
                    >
                        <table class="audit-table">

                            <thead>
                                <tr>
                                    <th>Fecha</th>
                                    <th>Acción</th>
                                    <th>Sobre</th>
                                    <th>Antes</th>
                                    <th>Después</th>
                                    <th>Resultado</th>
                                    <th>Usuario</th>
                                </tr>
                            </thead>

                            <tbody>

                                <tr
                                    v-for="row in audits"
                                    :key="row.id"
                                >
                                    <td>
                                        {{ formatDate(row.created_at) }}
                                    </td>

                                    <td>
                                        <strong>
                                            {{ auditLabel(row.action) }}
                                        </strong>
                                        <small
                                            v-if="row.message"
                                            class="audit-message"
                                        >
                                            {{ row.message }}
                                        </small>
                                    </td>

                                    <td class="serial">
                                        <small class="audit-type">
                                            {{ auditTargetType(row.target_type) }}
                                        </small>
                                        {{ row.target_id }}
                                    </td>

                                    <td class="audit-json">
                                        {{ auditValue(row.before) }}
                                    </td>

                                    <td class="audit-json">
                                        {{ auditValue(row.after) }}
                                    </td>

                                    <td>
                                        <span
                                            class="audit-result"
                                            :class="auditResultClass(row.result)"
                                        >
                                            {{ row.result }}
                                        </span>
                                    </td>

                                    <td>
                                        {{ row.username || '-' }}
                                    </td>
                                </tr>

                                <tr v-if="audits.length === 0">
                                    <td
                                        colspan="7"
                                        class="empty"
                                    >
                                        Aún no hay operaciones registradas.
                                    </td>
                                </tr>

                            </tbody>

                        </table>
                    </div>

                </section>
            </div>


            <!-- OVERLAY                                    -->
            <!-- ========================================= -->

            <div
                v-if="selectedDevice"
                class="overlay"
                @click="closeDevice"
            ></div>


            <!-- ========================================= -->
            <!-- FICHA ONU                                  -->
            <!-- ========================================= -->


            <div
                v-if="wanFormOpen"
                class="wan-form-overlay"
            >
                <div class="wan-form-modal">

                    <div class="wan-form-header">
                        <div>
                            <h2>
                                {{
                                    wanEditing
                                        ? (
                                            wanForm.type === 'pppoe'
                                                ? 'Editar WAN PPPoE'
                                                : wanForm.type === 'dhcp'
                                                    ? 'Editar WAN DHCP'
                                                    : 'Editar WAN IP fija'
                                          )
                                        : 'Nueva WAN'
                                }}
                            </h2>
                            <p>
                                {{
                                    wanEditing
                                        ? 'La WAN debe estar desactivada para editar.'
                                        : 'La nueva WAN se creará inicialmente desactivada.'

                                }}
                            </p>
                        </div>

                        <button
                            class="close-button"
                            @click="closeWanForm"
                        >
                            ×
                        </button>
                    </div>

                    <div class="wan-form-body">

                        <div class="wan-form-grid">

                            <!-- ACS_WAN_MULTITYPE_UI_14A2 -->
                            <div
                                v-if="!wanEditing"
                                class="wan-type-selector wide"
                            >
                                <button
                                    type="button"
                                    :class="{
                                        selected:
                                            wanForm.type === 'pppoe'
                                    }"
                                    @click="setWanType('pppoe')"
                                >
                                    PPPoE
                                </button>

                                <button
                                    type="button"
                                    :class="{
                                        selected:
                                            wanForm.type === 'dhcp'
                                    }"
                                    @click="setWanType('dhcp')"
                                >
                                    DHCP
                                </button>

                                <button
                                    type="button"
                                    :class="{
                                        selected:
                                            wanForm.type === 'static'
                                    }"
                                    @click="setWanType('static')"
                                >
                                    IP fija
                                </button>
                            </div>

                            <label>
                                VLAN
                                <input
                                    type="number"
                                    min="1"
                                    max="4094"
                                    v-model.number="wanForm.vlan"
                                />
                            </label>

                            <label>
                                Prioridad 802.1p
                                <select v-model.number="wanForm.priority">
                                    <option
                                        v-for="n in 8"
                                        :value="n-1"
                                    >
                                        {{ n-1 }}
                                    </option>
                                </select>
                            </label>

                            <label
                                v-if="wanForm.type === 'pppoe'"
                                class="wide"
                            >
                                Usuario PPPoE
                                <input
                                    v-model="wanForm.username"
                                    autocomplete="off"
                                />
                            </label>

                            <label
                                v-if="wanForm.type === 'pppoe'"
                                class="wide"
                            >
                                Contraseña PPPoE
                                <input
                                    type="password"
                                    v-model="wanForm.password"
                                    autocomplete="new-password"
                                />
                            </label>

                            <template
                                v-if="wanForm.type === 'static'"
                            >
                                <label class="wide">
                                    Dirección IP
                                    <input
                                        v-model="wanForm.ip"
                                        placeholder="192.0.2.10"
                                        autocomplete="off"
                                    />
                                </label>

                                <label>
                                    Máscara
                                    <input
                                        v-model="wanForm.subnet_mask"
                                        placeholder="255.255.255.0"
                                        autocomplete="off"
                                    />
                                </label>

                                <label>
                                    Gateway
                                    <input
                                        v-model="wanForm.gateway"
                                        placeholder="192.0.2.1"
                                        autocomplete="off"
                                    />
                                </label>

                                <label class="wide">
                                    DNS
                                    <input
                                        v-model="wanForm.dns"
                                        placeholder="8.8.8.8,1.1.1.1"
                                        autocomplete="off"
                                    />
                                </label>
                            </template>

                            <label>
                                MTU
                                <input
                                    type="number"
                                    :max="
                                        wanForm.type === 'pppoe'
                                            ? 1492
                                            : 1500
                                    "
                                    v-model.number="wanForm.mtu"
                                />
                            </label>

                            <label class="wan-check">
                                <input
                                    type="checkbox"
                                    v-model="wanForm.nat"
                                />
                                NAT habilitado
                            </label>

                        </div>

                        <h3>Interfaces asociadas</h3>

                        <div class="wan-interface-list">

                            <label
                                v-for="i in wanInterfaces"
                                :key="i.path"
                                class="wan-interface-item"
                            >
                                <input
                                    type="checkbox"
                                    :checked="
                                        wanForm.bindings.includes(i.path)
                                    "
                                    @change="toggleBinding(i.path)"
                                />

                                <span>
                                    {{
                                        i.type === 'wifi'
                                            ? '📶'
                                            : '🔌'
                                    }}
                                    {{ i.label }}
                                </span>

                                <small v-if="i.enabled === false">
                                    apagada
                                </small>
                            </label>

                        </div>

                        <div
                            v-if="wanMessage"
                            class="wan-form-message"
                        >
                            {{ wanMessage }}
                        </div>

                        <div class="wan-form-actions">

                            <button
                                class="wan-cancel"
                                @click="closeWanForm"
                                :disabled="wanCreating"
                            >
                                Cancelar
                            </button>

                            <button
                                class="wan-create"
                                @click="
                                    wanEditing
                                        ? editWan()
                                        : createWan()
                                "
                                :disabled="wanCreating"
                            >
                                {{
                                    wanCreating
                                        ? 'Procesando...'
                                        : wanEditing
                                            ? 'Guardar cambios'
                                            : 'Crear WAN desactivada'
                                }}
                            </button>

                        </div>

                    </div>

                </div>
            </div>


            <aside
                class="device-drawer"
                :class="{ open: selectedDevice }"
            >

                <template v-if="selectedDevice">

                    <div class="drawer-header">

                        <div>

                            <div class="drawer-status">

                                <span
                                    class="dot"
                                    :class="
                                        selectedDevice.online
                                            ? 'online-dot'
                                            : 'offline-dot'
                                    "
                                ></span>

                                {{
                                    selectedDevice.online
                                        ? 'EN LÍNEA'
                                        : 'FUERA DE LÍNEA'
                                }}

                            </div>


                            <h2>
                                {{
                                    selectedDevice.product_class
                                }}
                            </h2>


                            <p>
                                {{
                                    selectedDevice.manufacturer
                                }}
                                ·
                                {{
                                    selectedDevice.serial_number
                                }}
                            </p>

                            <div class="data-age">
                                <span v-if="dataStatus && dataStatus.updated_at">
                                    Datos leídos: {{ formatDate(dataStatus.updated_at) }}
                                </span>
                                <button
                                    class="data-reload"
                                    :disabled="['reading', 'updating', 'waiting'].includes(refreshState)"
                                    title="Volver a leer todos los datos desde la ONU (no cambia nada en el equipo)"
                                    @click="startRefresh(true)"
                                >
                                    ↻ Leer de la ONU
                                </button>
                            </div>

                        </div>


                        <button
                            class="close-button"
                            @click="closeDevice"
                        >
                            ×
                        </button>

                    </div>


                    <div
                        v-if="readOnly"
                        class="uncertified-banner"
                    >
                        ⚠ {{ certification.message }}
                    </div>

                    <div
                        v-if="refreshState"
                        class="refresh-banner"
                        :class="'refresh-' + refreshState"
                    >
                        <span
                            v-if="['reading', 'updating', 'waiting'].includes(refreshState) && !refreshMessage"
                            class="refresh-spinner"
                        ></span>

                        <span class="refresh-text">
                            <template v-if="refreshMessage">
                                {{ refreshMessage }}
                            </template>
                            <template v-else-if="refreshState === 'reading'">
                                Leyendo datos del equipo… La primera lectura de una ONU puede tardar unos segundos.
                            </template>
                            <template v-else-if="refreshState === 'updating'">
                                Actualizando datos desde la ONU…
                            </template>
                            <template v-else-if="refreshState === 'waiting'">
                                La ONU no respondió al instante. Los datos llegarán en su próximo reporte; esta vista se actualizará sola.
                            </template>
                            <template v-else-if="refreshState === 'done'">
                                Datos actualizados desde la ONU.
                            </template>
                        </span>

                        <button
                            v-if="refreshNewData"
                            class="refresh-action"
                            @click="reloadActiveTab"
                        >
                            Mostrar datos nuevos
                        </button>

                        <button
                            v-if="refreshState === 'error'"
                            class="refresh-action"
                            @click="startRefresh(true)"
                        >
                            Reintentar
                        </button>
                    </div>


                    <div class="tabs">

                        <button
                            :class="{
                                active:
                                    activeTab === 'resumen'
                            }"
                            @click="activeTab = 'resumen'"
                        >
                            Resumen
                        </button>

                        <button
                            :class="{
                                active:
                                    activeTab === 'internet'
                            }"
                            @click="openWan" "
                        >
                            Internet
                        </button>

                        <button
                            :class="{
                                active:
                                    activeTab === 'wifi'
                            }"
                            @click="openWifi" "
                        >
                            Wi-Fi
                        </button>

                        <button
                            :class="{
                                active:
                                    activeTab === 'catv'
                            }"
                            @click="openCatv" "
                        >
                            CATV
                        </button>

                        <button
                            :class="{
                                active:
                                    activeTab === 'seguridad'
                            }"
                            @click="openSecurity"
                        >
                            Seguridad
                        </button>

                    </div>


                    <div class="drawer-content">

                        <div
                            v-if="detailLoading"
                            class="loading"
                        >
                            <div class="spinner"></div>
                            Consultando ONU...
                        </div>


                        <template v-else>


                            <!-- RESUMEN -->

                            <div v-if="activeTab === 'resumen'">

                                <h3>
                                    Información del equipo
                                </h3>


                                <div class="info-grid">

                                    <div class="info-box">
                                        <span>Fabricante</span>
                                        <strong>
                                            {{
                                                selectedDevice.manufacturer
                                                || '-'
                                            }}
                                        </strong>
                                    </div>


                                    <div class="info-box">
                                        <span>Modelo</span>
                                        <strong>
                                            {{
                                                selectedDevice.product_class
                                                || '-'
                                            }}
                                        </strong>
                                    </div>


                                    <div class="info-box wide">
                                        <span>Número de serie</span>
                                        <strong class="mono">
                                            {{
                                                selectedDevice.serial_number
                                                || '-'
                                            }}
                                        </strong>
                                    </div>


                                    <div class="info-box">
                                        <span>OUI</span>
                                        <strong>
                                            {{
                                                selectedDevice.oui
                                                || '-'
                                            }}
                                        </strong>
                                    </div>


                                    <div class="info-box">
                                        <span>Hardware</span>
                                        <strong>
                                            {{
                                                selectedDevice.hardware_version
                                                || '-'
                                            }}
                                        </strong>
                                    </div>


                                    <div class="info-box wide">
                                        <span>Firmware</span>
                                        <strong>
                                            {{
                                                selectedDevice.software_version
                                                || '-'
                                            }}
                                        </strong>
                                    </div>


                                    <div class="info-box">
                                        <span>Uptime</span>
                                        <strong>
                                            {{
                                                formatUptime(
                                                    selectedDevice.uptime
                                                )
                                            }}
                                        </strong>
                                    </div>


                                    <div class="info-box">
                                        <span>Estado</span>

                                        <strong
                                            :class="
                                                selectedDevice.online
                                                    ? 'text-green'
                                                    : 'text-red'
                                            "
                                        >
                                            {{
                                                selectedDevice.online
                                                    ? 'En línea'
                                                    : 'Fuera de línea'
                                            }}
                                        </strong>

                                    </div>


                                    <div class="info-box wide">
                                        <span>Último Inform</span>

                                        <strong>
                                            {{
                                                formatDate(
                                                    selectedDevice.last_inform
                                                )
                                            }}
                                        </strong>
                                    </div>

                                </div>


                                
                            
                            <div class="device-tags-box">

                                <span class="device-tags-title">
                                    Etiquetas GenieACS
                                </span>

                                <div
                                    v-if="
                                        selectedDevice.tags
                                        && selectedDevice.tags.length
                                    "
                                    class="tags-row"
                                >
                                    <span
                                        v-for="tag in selectedDevice.tags"
                                        :key="tag"
                                        class="tag-chip tag-editable"
                                    >
                                        {{ tag }}

                                        <button
                                            @click="removeTag(tag)"
                                            :disabled="tagBusy"
                                            title="Eliminar etiqueta"
                                        >
                                            ×
                                        </button>
                                    </span>
                                </div>

                                <span
                                    v-else
                                    class="no-tags"
                                >
                                    Sin etiquetas
                                </span>

                                <div class="tag-add-row">

                                    <input
                                        v-model="newTag"
                                        @keyup.enter="addTag"
                                        maxlength="64"
                                        placeholder="Nueva etiqueta"
                                    />

                                    <button
                                        @click="addTag"
                                        :disabled="
                                            tagBusy
                                            || !newTag.trim()
                                        "
                                    >
                                        + Agregar
                                    </button>

                                </div>

                            </div>




                            </div>


                            
                            
                            <!-- WIFI REAL -->
                            <!-- ACS_WIFI_EDITOR_15B2A -->

                            <div
                                v-else-if="
                                    activeTab === 'wifi'
                                "
                                class="wifi-editor"
                            >

                                <div class="wifi-editor-head">

                                    <div>
                                        <h3>
                                            Configuración Wi-Fi
                                        </h3>

                                        <p>
                                            Radios principales
                                            de la ONU
                                        </p>
                                    </div>

                                </div>


                                <div
                                    v-if="wifiLoading"
                                    class="loading"
                                >
                                    <div
                                        class="spinner"
                                    ></div>

                                    Leyendo Wi-Fi
                                    desde la ONU...
                                </div>


                                <div
                                    v-else-if="wifiError"
                                    class="error-message"
                                >
                                    {{ wifiError }}
                                </div>


                                <div
                                    v-else
                                    class="wifi-editor-grid"
                                >

                                    <template
                                        v-for="(form, index) in wifiForms"
                                        :key="index"
                                    >

                                        <div
                                            v-if="
                                                wifiForms[
                                                    index
                                                ]
                                            "
                                            class="
                                                wifi-editor-card
                                            "
                                        >

                                            <div
                                                class="
                                                    wifi-editor-top
                                                "
                                            >

                                                <div>

                                                    <small>
                                                        📶 Wi-Fi
                                                    </small>

                                                    <h3>
                                                        {{
                                                            wifiForms[
                                                                index
                                                            ].band
                                                        }}
                                                    </h3>

                                                    <span
                                                        class="
                                                            wifi-wlan-id
                                                        "
                                                    >
                                                        WLANConfiguration.
                                                        {{ index }}
                                                    </span>

                                                </div>


                                                <label
                                                    class="
                                                        wifi-toggle
                                                    "
                                                >

                                                    <input
                                                        type="checkbox"
                                                        v-model="
                                                            wifiForms[
                                                                index
                                                            ].enabled
                                                        "
                                                    >

                                                    <strong>
                                                        {{
                                                            wifiForms[
                                                                index
                                                            ].enabled
                                                                ? 'Activo'
                                                                : 'Apagado'
                                                        }}
                                                    </strong>

                                                </label>

                                            </div>


                                            <div
                                                class="
                                                    wifi-field
                                                "
                                            >

                                                <label>
                                                    Nombre Wi-Fi
                                                </label>

                                                <input
                                                    type="text"
                                                    maxlength="32"
                                                    v-model="
                                                        wifiForms[
                                                            index
                                                        ].ssid
                                                    "
                                                >

                                            </div>


                                            <div
                                                class="
                                                    wifi-field
                                                "
                                            >

                                                <label>
                                                    Nueva contraseña
                                                </label>

                                                <input
                                                    type="password"
                                                    minlength="8"
                                                    maxlength="63"
                                                    autocomplete="
                                                        new-password
                                                    "
                                                    placeholder="
                                                        Dejar vacío para conservar
                                                    "
                                                    v-model="
                                                        wifiForms[
                                                            index
                                                        ].password
                                                    "
                                                >

                                                <small>
                                                    La clave actual
                                                    nunca se muestra.
                                                </small>

                                            </div>


                                            <div
                                                class="
                                                    wifi-option
                                                "
                                            >

                                                <label>

                                                    <input
                                                        type="checkbox"
                                                        v-model="
                                                            wifiForms[
                                                                index
                                                            ].auto_channel
                                                        "
                                                    >

                                                    Canal automático

                                                </label>

                                            </div>


                                            <div
                                                v-if="
                                                    wifiForms[
                                                        index
                                                    ].auto_channel
                                                "
                                                class="
                                                    wifi-channel-info
                                                "
                                            >

                                                Canal actual

                                                <strong>
                                                    {{
                                                        wifiForms[
                                                            index
                                                        ].current_channel
                                                        || '-'
                                                    }}
                                                </strong>

                                            </div>


                                            <div
                                                v-else
                                                class="
                                                    wifi-field
                                                "
                                            >

                                                <label>
                                                    Canal
                                                </label>

                                                <select
                                                    v-model.number="
                                                        wifiForms[
                                                            index
                                                        ].channel
                                                    "
                                                >

                                                    <option
                                                        :value="0"
                                                        disabled
                                                    >
                                                        Seleccionar
                                                    </option>

                                                    <option
                                                        v-for="
                                                            channel
                                                            in wifiChannels(
                                                                index
                                                            )
                                                        "
                                                        :key="
                                                            channel
                                                        "
                                                        :value="
                                                            channel
                                                        "
                                                    >
                                                        Canal
                                                        {{ channel }}
                                                    </option>

                                                </select>

                                            </div>


                                            <div
                                                class="
                                                    wifi-option
                                                "
                                            >

                                                <label>

                                                    <input
                                                        type="checkbox"
                                                        v-model="
                                                            wifiForms[
                                                                index
                                                            ].hidden
                                                        "
                                                    >

                                                    Ocultar SSID

                                                </label>

                                            </div>


                                            <div
                                                class="
                                                    wifi-summary
                                                "
                                            >

                                                <div>
                                                    <span>
                                                        Estándar
                                                    </span>

                                                    <strong>
                                                        {{
                                                            wifiForms[
                                                                index
                                                            ].standard
                                                            || '-'
                                                        }}
                                                    </strong>
                                                </div>


                                                <div>
                                                    <span>
                                                        Seguridad
                                                    </span>

                                                    <strong>
                                                        {{
                                                            wifiForms[
                                                                index
                                                            ].encryption
                                                            || '-'
                                                        }}
                                                    </strong>
                                                </div>

                                            </div>


                                            <div
                                                v-if="
                                                    wifiMessage[
                                                        index
                                                    ]
                                                "
                                                class="
                                                    wifi-save-message
                                                "
                                            >
                                                {{
                                                    wifiMessage[
                                                        index
                                                    ]
                                                }}
                                            </div>


                                            <button
                                                class="
                                                    wifi-save-btn
                                                "
                                                :disabled="
                                                    wifiBusy
                                                    === index
                                                "
                                                @click="
                                                    saveWifi(
                                                        index
                                                    )
                                                "
                                            >

                                                {{
                                                    wifiBusy
                                                    === index
                                                        ? 'Guardando...'
                                                        : 'Guardar cambios'
                                                }}

                                            </button>

                                        </div>

                                    </template>

                                </div>

                            </div>


                            <!-- CATV REAL -->

                            <div
                                v-else-if="activeTab === 'catv'"
                            >
                                <div
                                    v-if="catvLoading"
                                    class="loading"
                                >
                                    <div class="spinner"></div>
                                    Consultando CATV...
                                </div>

                                <div
                                    v-else-if="catvError"
                                    class="error-message"
                                >
                                    {{ catvError }}
                                </div>

                                <template v-else-if="catv">

                                    <div class="info-grid">

                                        <div class="info-box">
                                            <span>Soporte CATV</span>
                                            <strong>
                                                {{
                                                    catv.supported
                                                        ? 'Sí'
                                                        : 'No'
                                                }}
                                            </strong>
                                        </div>

                                        <div class="info-box">
                                            <span>Estado</span>
                                            <strong>
                                                {{
                                                    catvState(
                                                        catv.enabled
                                                    )
                                                }}
                                            </strong>
                                        </div>

                                        <div
                                            v-for="metric in (catv.metrics || [])"
                                            :key="metric.label"
                                            class="info-box"
                                        >
                                            <span>{{ metric.label }}</span>
                                            <strong>{{ metric.value }}</strong>
                                        </div>

                                    </div>

                                    <small
                                        v-if="catv.driver === 'x_rz_catv' && !(catv.metrics || []).length"
                                    >
                                        Esta ONU no reporta mediciones de RF por TR-069
                                        (potencia, nivel de salida, AGC).
                                    </small>

                                    <div class="catv-control-box">

                                        <strong>
                                            Control CATV
                                        </strong>

                                        <p>
                                            Estado reportado:
                                            <b>{{ catvState(catv.enabled) }}</b>
                                        </p>

                                        <div class="catv-buttons">

                                            <button
                                                class="catv-on"
                                                :disabled="catvBusy"
                                                @click="setCatv('on')"
                                            >
                                                {{
                                                    catvBusy
                                                        ? 'Procesando...'
                                                        : 'Activar CATV'
                                                }}
                                            </button>

                                            <button
                                                class="catv-off"
                                                :disabled="catvBusy"
                                                @click="setCatv('off')"
                                            >
                                                {{
                                                    catvBusy
                                                        ? 'Procesando...'
                                                        : 'Desactivar CATV'
                                                }}
                                            </button>

                                        </div>

                                        <small>
                                            GenieACS escribirá directamente
                                            {{ (catv.parameter || 'Catv.Enable').split('.').slice(-2).join('.') }}.
                                        </small>

                                    </div>

                                </template>

                            </div>


                            <!-- SEGURIDAD REAL 16B2 -->

                            <div
                                v-else-if="
                                    activeTab === 'seguridad'
                                "
                                class="security-module"
                            >

                                <div
                                    v-if="securityLoading"
                                    class="loading"
                                >

                                    <div
                                        class="spinner"
                                    ></div>

                                    Consultando seguridad...

                                </div>


                                <div
                                    v-else-if="securityError"
                                    class="error-message"
                                >
                                    {{ securityError }}
                                </div>


                                <template
                                    v-else-if="
                                        securityData &&
                                        securityData.supported
                                    "
                                >

                                    <div
                                        v-if="(securityData.notes || []).length"
                                        class="info-grid"
                                    >
                                        <div
                                            v-for="note in securityData.notes"
                                            :key="note.label"
                                            class="info-box"
                                        >
                                            <span>{{ note.label }}</span>
                                            <strong>{{ note.value }}</strong>
                                        </div>
                                    </div>

                                    <!-- FIREWALL -->

                                    <div v-if="securityData.firewall_kind"
                                        class="
                                            security-firewall-card
                                        "
                                    >

                                        <div
                                            class="
                                                security-firewall-head
                                            "
                                        >

                                            <div>

                                                <small>
                                                    🛡 FIREWALL
                                                </small>

                                                <h3>
                                                    Nivel de seguridad
                                                </h3>

                                                <p>
                                                    Control general
                                                    de acceso WAN.
                                                </p>

                                            </div>


                                            <span
                                                class="
                                                    security-grade-badge
                                                "
                                            >
                                                {{
                                                    securityData
                                                    .firewall_label
                                                }}
                                            </span>

                                        </div>


                                        <div
                                            class="
                                                security-grade-buttons
                                            "
                                        >

                                            <button
                                                :class="{
                                                    active:
                                                        securityData
                                                        .firewall_grade
                                                        === 0
                                                }"
                                                :disabled="
                                                    securityBusy
                                                    === 'firewall'
                                                    ||
                                                    !securityData
                                                    .firewall_writable
                                                "
                                                @click="
                                                    setFirewallGrade(0)
                                                "
                                            >

                                                <strong>
                                                    {{ securityData.firewall_kind === 'cmcc' ? 'Apagar' : 'Bajo' }}
                                                </strong>

                                                <small>
                                                    {{ securityData.firewall_kind === 'cmcc' ? 'Firewall apagado' : 'Nivel 0' }}
                                                </small>

                                            </button>


                                            <button
                                                :class="{
                                                    active:
                                                        securityData
                                                        .firewall_grade
                                                        === 1
                                                }"
                                                :disabled="
                                                    securityBusy
                                                    === 'firewall'
                                                    ||
                                                    !securityData
                                                    .firewall_writable
                                                "
                                                @click="
                                                    setFirewallGrade(1)
                                                "
                                            >

                                                <strong>
                                                    {{ securityData.firewall_kind === 'cmcc' ? 'Encender' : 'Alto' }}
                                                </strong>

                                                <small>
                                                    {{ securityData.firewall_kind === 'cmcc' ? 'Firewall encendido' : 'Nivel 1' }}
                                                </small>

                                            </button>

                                        </div>


                                        <div
                                            class="
                                                security-firewall-info
                                            "
                                            :class="{
                                                blocked:
                                                    securityData
                                                    .firewall_grade
                                                    !== 0
                                            }"
                                        >

                                            <strong
                                                v-if="
                                                    securityData
                                                    .firewall_grade
                                                    === 0
                                                "
                                            >
                                                ✓ Activaciones WAN permitidas
                                            </strong>


                                            <strong
                                                v-else
                                            >
                                                🔒 Nuevas activaciones WAN bloqueadas
                                            </strong>


                                            <span>
                                                {{
                                                    securityData
                                                    .firewall_grade
                                                    === 0
                                                        ? 'Puedes habilitar HTTP, HTTPS, SSH y demás servicios por WAN.'
                                                        : 'Primero debes cambiar el firewall a Bajo para habilitar un servicio por WAN.'
                                                }}
                                            </span>

                                        </div>

                                    </div>


                                    <!-- TR069 PROTEGIDO -->

                                    <div
                                        class="security-tr069"
                                    >

                                        <span
                                            class="
                                                security-lock-icon
                                            "
                                        >
                                            🔒
                                        </span>

                                        <div>

                                            <strong>
                                                Gestión TR-069 protegida
                                            </strong>

                                            <span>
                                                ACS Control no modifica
                                                CWMP ni ManagementServer
                                                desde este módulo.
                                            </span>

                                        </div>

                                    </div>


                                    <!-- SERVICIOS -->

                                    <div
                                        class="
                                            security-services-header
                                        "
                                    >

                                        <h3>
                                            Acceso al equipo
                                        </h3>

                                        <p>
                                            Control de servicios
                                            disponibles desde LAN y WAN.
                                        </p>

                                    </div>


                                    <div
                                        class="
                                            security-services-grid
                                        "
                                    >

                                        <div
                                            v-for="
                                                service
                                                in securityData.services
                                            "
                                            :key="
                                                service.id
                                            "
                                            class="
                                                security-service-card
                                            "
                                        >

                                            <div
                                                class="
                                                    security-service-title
                                                "
                                            >

                                                <div>

                                                    <strong>
                                                        {{
                                                            service.label
                                                        }}
                                                    </strong>

                                                    <small
                                                        :class="
                                                            'security-risk-'
                                                            + service.risk
                                                        "
                                                    >

                                                        {{
                                                            service.risk
                                                            === 'high'
                                                                ? 'Exposición alta'
                                                                : service.risk
                                                                === 'medium'
                                                                    ? 'Acceso administrativo'
                                                                    : 'Diagnóstico'
                                                        }}

                                                    </small>

                                                </div>


                                                <span
                                                    v-if="
                                                        service
                                                        .wan_enabled
                                                    "
                                                    class="
                                                        security-wan-open
                                                    "
                                                >
                                                    WAN ACTIVO
                                                </span>

                                            </div>


                                            <!-- LAN / WAN -->

                                            <div
                                                class="
                                                    security-toggle-grid
                                                "
                                            >

                                                <div>

                                                    <span>
                                                        LAN
                                                    </span>

                                                    <button
                                                        :class="{
                                                            on:
                                                                service
                                                                .lan_enabled
                                                        }"
                                                        :disabled="
                                                            !service
                                                            .lan_writable
                                                            ||
                                                            securityBusy
                                                            === service.id
                                                        "
                                                        @click="
                                                            toggleSecurityLan(
                                                                service
                                                            )
                                                        "
                                                    >

                                                        {{
                                                            service
                                                            .lan_enabled
                                                                ? 'ACTIVO'
                                                                : 'APAGADO'
                                                        }}

                                                    </button>

                                                </div>


                                                <div>

                                                    <span>
                                                        WAN
                                                    </span>

                                                    <button
                                                        :class="{
                                                            on:
                                                                service
                                                                .wan_enabled,

                                                            blocked:
                                                                !service
                                                                .wan_enabled
                                                                &&
                                                                securityData
                                                                .firewall_grade
                                                                !== 0
                                                        }"
                                                        :disabled="
                                                            !service
                                                            .wan_writable
                                                            ||
                                                            securityBusy
                                                            === service.id
                                                            ||
                                                            (
                                                                !service
                                                                .wan_enabled
                                                                &&
                                                                securityData
                                                                .firewall_grade
                                                                !== 0
                                                            )
                                                        "
                                                        @click="
                                                            toggleSecurityWan(
                                                                service
                                                            )
                                                        "
                                                    >

                                                        {{
                                                            service
                                                            .wan_enabled
                                                                ? 'ACTIVO'
                                                                : securityData
                                                                    .firewall_grade
                                                                    !== 0
                                                                    ? 'BLOQUEADO'
                                                                    : 'APAGADO'
                                                        }}

                                                    </button>

                                                </div>

                                            </div>


                                            <!-- PUERTO -->

                                            <div
                                                v-if="
                                                    service
                                                    .port_supported
                                                "
                                                class="
                                                    security-field
                                                "
                                            >

                                                <label>
                                                    Puerto WAN
                                                </label>

                                                <input
                                                    type="number"
                                                    min="1"
                                                    max="65535"
                                                    v-model.number="
                                                        service
                                                        .wan_port
                                                    "
                                                    :disabled="
                                                        !service
                                                        .port_writable
                                                    "
                                                >

                                            </div>


                                            <!-- IP -->

                                            <div
                                                v-if="
                                                    service
                                                    .ip_supported
                                                "
                                                class="
                                                    security-field
                                                "
                                            >

                                                <label>
                                                    IP permitida
                                                </label>

                                                <input
                                                    type="text"
                                                    placeholder="
                                                        Vacío = cualquier IP
                                                    "
                                                    v-model="
                                                        service
                                                        .specific_ip
                                                    "
                                                    :disabled="
                                                        !service
                                                        .ip_writable
                                                    "
                                                >

                                            </div>


                                            <button
                                                v-if="
                                                    service
                                                    .port_supported
                                                    ||
                                                    service
                                                    .ip_supported
                                                "
                                                class="
                                                    security-save-btn
                                                "
                                                :disabled="
                                                    securityBusy
                                                    === service.id
                                                "
                                                @click="
                                                    saveSecurityDetails(
                                                        service
                                                    )
                                                "
                                            >

                                                {{
                                                    securityBusy
                                                    === service.id
                                                        ? 'Guardando...'
                                                        : 'Guardar ajustes'
                                                }}

                                            </button>

                                        </div>

                                    </div>


                                    <div
                                        v-if="
                                            securityMessage
                                        "
                                        class="
                                            security-message
                                        "
                                    >
                                        {{ securityMessage }}
                                    </div>

                                </template>


                                <div
                                    v-else
                                    class="warning-box"
                                >

                                    {{
                                        securityData && securityData.reason
                                            ? securityData.reason
                                            : 'Esta ONU no expone controles de seguridad compatibles.'
                                    }}

                                    <div
                                        v-for="note in ((securityData && securityData.notes) || [])"
                                        :key="note.label"
                                    >
                                        <b>{{ note.label }}:</b> {{ note.value }}
                                    </div>

                                </div>

                            </div>



                            
                            <!-- WAN REAL -->

                            <div
                                v-else-if="activeTab === 'internet'"
                            >

                                <div
                                    v-if="wanLoading"
                                    class="loading"
                                >
                                    <div class="spinner"></div>
                                    Consultando conexiones WAN...
                                </div>

                                <div
                                    v-else-if="wanError"
                                    class="error-message"
                                >
                                    {{ wanError }}
                                </div>

                                <template v-else-if="wan">

                                    <div class="section-heading">
                                        <div>
                                            <h3>
                                                Conexiones WAN
                                            </h3>

                                            <p>
                                                {{ wan.count }}
                                                conexión(es) detectada(s)
                                            </p>
                                        </div>

                                        <button
                                            class="wan-add-button"
                                            @click="openWanForm"
                                        >
                                            + Agregar WAN
                                        </button>
                                    </div>

                                    <div
                                        v-for="connection in wan.wan"
                                        :key="
                                            connection.wan_connection_device
                                            + '-'
                                            + connection.object_type
                                            + '-'
                                            + connection.instance
                                        "
                                        class="wan-card"
                                    >

                                        <div class="wan-header">

                                            <div>
                                                <small>
                                                    🌐 WAN
                                                    {{
                                                        connection.wan_connection_device
                                                    }}
                                                </small>

                                                <h3>
                                                    {{
                                                        connection.type
                                                    }}
                                                    ·
                                                    {{
                                                        connection.mode
                                                    }}
                                                </h3>

                                                <p>
                                                    {{
                                                        serviceText(
                                                            connection.services
                                                        )
                                                    }}
                                                </p>
                                            </div>

                                            <span
                                                class="wan-state"
                                                :class="
                                                    connection.status
                                                    === 'Connected'
                                                        ? 'connected'
                                                        : 'disconnected'
                                                "
                                            >
                                                {{
                                                    connection.status
                                                    || 'Sin estado'
                                                }}
                                            </span>

                                        </div>

                                        <!-- ACS_WAN_TOGGLE_UI_12E2 -->
                                        <div class="wan-controls">

                                            <div
                                                v-if="connection.protected"
                                                class="wan-protected"
                                            >
                                                🛡 WAN protegida · TR-069
                                            </div>

                                            <button
                                                v-if="
                                                    !connection.protected
                                                    && (
                                                        connection.object_type
                                                        === 'WANPPPConnection'
                                                        || connection.object_type
                                                        === 'WANIPConnection'
                                                    )
                                                "
                                                class="wan-edit-button"
                                                :disabled="
                                                    wanDeleteBusy
                                                    === connection.wan_connection_device
                                                "
                                                @click="
                                                    openWanEdit(connection)
                                                "
                                                title="Editar WAN"
                                            >
                                                Editar WAN
                                            </button>

                                            <button
                                                v-if="
                                                    !connection.protected
                                                    && (
                                                        connection.object_type
                                                        === 'WANPPPConnection'
                                                        || connection.object_type
                                                        === 'WANIPConnection'
                                                    )
                                                "
                                                class="wan-delete-button"
                                                :disabled="
                                                    wanDeleteBusy
                                                    === connection.wan_connection_device
                                                "
                                                @click="
                                                    deleteWan(connection)
                                                "
                                            >
                                                {{
                                                    wanDeleteBusy
                                                    === connection.wan_connection_device
                                                        ? 'Eliminando...'
                                                        : 'Eliminar WAN'
                                                }}
                                            </button>

                                        </div>

                                        <div class="wan-grid">

                                            <div>
                                                <span>VLAN</span>
                                                <strong>
                                                    {{
                                                        connection.vlan
                                                        ?? '-'
                                                    }}
                                                </strong>
                                            </div>

                                            <div>
                                                <span>802.1p</span>
                                                <strong>
                                                    {{
                                                        connection.priority_8021p
                                                        ?? 'Sin marcar'
                                                    }}
                                                </strong>
                                            </div>

                                            <div>
                                                <span>NAT</span>
                                                <strong>
                                                    {{
                                                        connection.nat
                                                            ? 'Activado'
                                                            : 'Desactivado'
                                                    }}
                                                </strong>
                                            </div>

                                            <div>
                                                <span>MTU</span>
                                                <strong>
                                                    {{
                                                        connection.mtu
                                                        || '-'
                                                    }}
                                                </strong>
                                            </div>

                                            <div v-if="connection.username">
                                                <span>Usuario PPPoE</span>
                                                <strong>
                                                    {{
                                                        connection.username
                                                    }}
                                                </strong>
                                            </div>

                                            <div>
                                                <span>Dirección IP</span>
                                                <strong>
                                                    {{
                                                        connection.ip
                                                        || '-'
                                                    }}
                                                </strong>
                                            </div>

                                            <div>
                                                <span>Gateway</span>
                                                <strong>
                                                    {{
                                                        connection.gateway
                                                        || '-'
                                                    }}
                                                </strong>
                                            </div>

                                            <div>
                                                <span>DNS</span>
                                                <strong>
                                                    {{
                                                        connection.dns
                                                        || '-'
                                                    }}
                                                </strong>
                                            </div>

                                            <!-- ACS_WAN_BINDINGS_UI_11E -->
                                            <div class="wan-wide">
                                                <span>
                                                    Interfaces asociadas
                                                </span>

                                                <div
                                                    v-if="
                                                        connection.bindings
                                                        && connection.bindings.length
                                                    "
                                                    class="binding-list"
                                                >
                                                    <span
                                                        v-for="b in connection.bindings"
                                                        :key="b.type + b.index"
                                                        class="binding-chip"
                                                        :class="{
                                                            disabled:
                                                                b.enabled === false
                                                        }"
                                                    >
                                                        {{
                                                            b.type === 'wifi'
                                                                ? '📶 ' + b.label
                                                                : '🔌 ' + b.label
                                                        }}

                                                        <small
                                                            v-if="
                                                                b.type === 'wifi'
                                                                && b.enabled === false
                                                            "
                                                        >
                                                            apagado
                                                        </small>
                                                    </span>
                                                </div>

                                                <strong v-else>
                                                    Sin interfaces asociadas
                                                </strong>
                                            </div>

                                            <div class="wan-wide">
                                                <span>
                                                    Nombre interno
                                                </span>

                                                <strong>
                                                    {{
                                                        connection.name
                                                        || '-'
                                                    }}
                                                </strong>
                                            </div>

                                        </div>

                                    </div>

                                </template>

                            </div>


                            <!-- FUTURAS SECCIONES -->

                            <div
                                v-else
                                class="coming-section"
                            >

                                <div class="coming-icon">

                                    {{
                                        activeTab === 'internet'
                                            ? '🌐'
                                            : activeTab === 'wifi'
                                            ? '📶'
                                            : activeTab === 'catv'
                                            ? '📺'
                                            : '🔐'
                                    }}

                                </div>


                                <h3>

                                    {{
                                        activeTab === 'internet'
                                            ? 'Configuración de Internet'
                                            : activeTab === 'wifi'
                                            ? 'Configuración Wi-Fi'
                                            : activeTab === 'catv'
                                            ? 'Servicio CATV'
                                            : 'Seguridad y Firewall'
                                    }}

                                </h3>


                                <p>
                                    La interfaz ya está preparada.
                                    En la siguiente etapa conectaremos
                                    esta sección con los parámetros
                                    TR-069 reales del modelo.
                                </p>


                                <div class="read-only-badge">
                                    SOLO LECTURA
                                </div>

                            </div>

                        </template>

                    </div>

                </template>

            </aside>

        </div>
    `
}).mount('#app')
