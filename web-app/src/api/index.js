import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 静态数据回退
const getStaticData = async (filename) => {
  const resp = await fetch(`/data/${filename}`)
  if (!resp.ok) throw new Error(`Static data not found: ${filename}`)
  return { data: await resp.json() }
}

// 获取所有型号（从静态数据库）
export const getModels = async () => {
  try {
    return await api.get('/models/')
  } catch (e) {
    console.warn('API failed, using static data:', e.message)
    // 从index.json获取型号列表
    const indexData = await getStaticData('index.json')
    return { data: indexData.data.map(item => item.model) }
  }
}

// 获取型号详情（从静态JSON文件）
export const getModelDetail = async (name) => {
  try {
    return await api.get(`/models/${encodeURIComponent(name)}`)
  } catch (e) {
    console.warn('API failed, using static data:', e.message)
    const safeName = name.replace(/ /g, '_').replace(/\//g, '_')
    return getStaticData(`${safeName}.json`)
  }
}

// 获取型号趋势
export const getModelTrend = async (name, days = 30) => {
  try {
    return await api.get(`/models/${encodeURIComponent(name)}/trend`, { params: { days } })
  } catch (e) {
    console.warn('API failed, using static data:', e.message)
    const detail = await getModelDetail(name)
    return { data: detail.data.condition_trends || {} }
  }
}

// 获取记录列表
export const getRecords = async (params) => {
  try {
    return await api.get('/records/', { params })
  } catch (e) {
    console.warn('API failed, using static data:', e.message)
    return { data: [] }
  }
}

// 获取单条记录
export const getRecord = async (id) => {
  try {
    return await api.get(`/records/${id}`)
  } catch (e) {
    console.warn('API failed:', e.message)
    return { data: null }
  }
}

// 获取统计数据（从静态stats.json）
export const getStats = async () => {
  try {
    return await api.get('/stats/')
  } catch (e) {
    console.warn('API failed, using static data:', e.message)
    return getStaticData('stats.json')
  }
}

// 获取品牌统计
export const getBrandStats = async () => {
  try {
    return await api.get('/stats/brands')
  } catch (e) {
    console.warn('API failed:', e.message)
    return { data: {} }
  }
}

// 获取成色统计
export const getConditionStats = async () => {
  try {
    return await api.get('/stats/conditions')
  } catch (e) {
    console.warn('API failed:', e.message)
    return { data: {} }
  }
}

// 获取完整产品库（从静态index.json）
export const getRacketDatabase = async () => {
  try {
    return await api.get('/database/')
  } catch (e) {
    console.warn('API failed, using static data:', e.message)
    return getStaticData('index.json')
  }
}

// 获取品牌列表
export const getBrands = async () => {
  try {
    return await api.get('/database/brands')
  } catch (e) {
    console.warn('API failed:', e.message)
    return { data: ['YONEX', '李宁', 'VICTOR'] }
  }
}

export default api
