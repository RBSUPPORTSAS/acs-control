import {
    createApp,
    ref,
    computed,
    onMounted,
    onUnmounted
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


        // ====================================================
        // API
        // ====================================================

        
        async function openAudit() {
            auditOpen.value = true
            auditLoading.value = true

            try {
                const r = await fetch(
                    '/api/audit?limit=200',
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

            if (typeof value === 'object')
                return JSON.stringify(value)

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
                }

            } catch (e) {
                console.error(e)
            }

            detailLoading.value = false
        }


        
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


function closeDevice() {
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

            if (connection.enabled) {
                alert('Desactiva la WAN antes de editarla.')
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
            wanMessage.value = ''

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

                    if (!isVsol) {
                        throw new Error(
                            'IP fija por ahora está validada únicamente para VSOL.'
                        )
                    }

                    endpoint =
                        `/api/devices/${id}/wan/vsol/create-ip`

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

            if (connection.enabled) {
                alert(
                    'Desactiva la WAN antes de eliminarla.'
                )
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

                await openWan()

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

            if (Number(index) === 5) {

                return [
                    1, 2, 3, 4, 5, 6,
                    7, 8, 9, 10, 11
                ]
            }

            return [
                36, 40, 44, 48,
                52, 56, 60, 64,
                100, 104, 108, 112,
                116,
                136, 140,
                149, 153, 157, 161
            ]
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

                const radios = [
                    {
                        index: 1,
                        band: '5 GHz',
                        data: raw['5ghz']
                    },
                    {
                        index: 5,
                        band: '2.4 GHz',
                        data: raw['2_4ghz']
                    }
                ]

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


        onMounted(async () => {

            await Promise.all([
                loadHealth(),
                loadDevices()
            ])

            refreshTimer = setInterval(
                refreshAll,
                30000
            )
        })


        onUnmounted(() => {

            if (refreshTimer) {
                clearInterval(refreshTimer)
            }
        })


        return {
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

            formatDate,
            formatUptime
        }
    },


    template: `
        <div class="layout">

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
                        class="nav-item"
                        @click="openAudit"
                    >
                        <span class="nav-icon">↺</span>
                        Auditoría
                    </button>



                    <div class="nav-section">
                        SISTEMA
                    </div>

                    <button
                        class="nav-item"
                        @click="openConfig"
                    >
                        <span class="nav-icon">⚙</span>
                        Configuración
                    </button>

                </nav>


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

            <main class="main">

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

                    <div class="stat-card">

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


                    <div class="stat-card">

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


                    <div class="stat-card">

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


                    <div class="stat-card">

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

            

            <!-- CONFIGURACION 17A2 -->

            <div
                v-if="configOpen"
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
                v-if="auditOpen"
                class="audit-overlay"
            >
                <section class="audit-panel">

                    <div class="audit-header">

                        <div>
                            <h2>Auditoría</h2>
                            <p>
                                Historial de operaciones realizadas
                                desde ACS Control
                            </p>
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
                                    <th>Dispositivo</th>
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
                                            {{ row.action }}
                                        </strong>
                                    </td>

                                    <td class="serial">
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
                                            :class="row.result" "
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

                        </div>


                        <button
                            class="close-button"
                            @click="closeDevice"
                        >
                            ×
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


<div class="warning-box">

                                    <strong>
                                        Modo seguro
                                    </strong>

                                    <p>
                                        ACS Control está actualmente
                                        en modo solo lectura.
                                        Ninguna configuración de esta ONU
                                        puede modificarse todavía.
                                    </p>

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
                                        v-for="
                                            index in [1, 5]
                                        "
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

                                    </div>

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
                                            Catv.Enable = 1 o 0.
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

                                    <!-- FIREWALL -->

                                    <div
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
                                                    Bajo
                                                </strong>

                                                <small>
                                                    Nivel 0
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
                                                    Alto
                                                </strong>

                                                <small>
                                                    Nivel 1
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

                                    Esta ONU no expone
                                    controles de seguridad
                                    compatibles.

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
                                                v-else-if="
                                                    connection.object_type
                                                    === 'WANPPPConnection'
                                                    ||
                                                    connection.object_type
                                                    === 'WANIPConnection'
                                                "
                                                class="wan-toggle-button"
                                                :class="{
                                                    active:
                                                        connection.enabled
                                                }"
                                                :disabled="
                                                    wanToggleBusy
                                                    === connection.wan_connection_device
                                                "
                                                @click="toggleWan(connection)"
                                            >
                                                {{
                                                    wanToggleBusy
                                                    === connection.wan_connection_device
                                                        ? 'Procesando...'
                                                        : connection.enabled
                                                            ? 'Desactivar WAN'
                                                            : 'Activar WAN'
                                                }}
                                            </button>

                                            <button
                                                v-if="
                                                    !connection.protected
                                                    && (
                                                        connection.object_type
                                                        === 'WANPPPConnection'
                                                        ||
                                                        connection.object_type
                                                        === 'WANIPConnection'
                                                    )
                                                "
                                                class="wan-edit-button"
                                                :disabled="
                                                    connection.enabled
                                                    || wanToggleBusy
                                                    === connection.wan_connection_device
                                                "
                                                @click="
                                                    openWanEdit(connection)
                                                "
                                                :title="
                                                    connection.enabled
                                                        ? 'Desactiva la WAN para editar'
                                                        : 'Editar WAN'
                                                "
                                            >
                                                {{
                                                    connection.enabled
                                                        ? 'Desactiva para editar'
                                                        : 'Editar WAN'
                                                }}
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
                                                    connection.enabled
                                                    || wanDeleteBusy
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
                                                        : connection.enabled
                                                            ? 'Desactiva para eliminar'
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
                                                        ?? '-'
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
