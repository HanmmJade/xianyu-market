import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 获取所有型号
export const getModels = () => api.get('/models/')

// 获取型号详情
export const getModelDetail = (name) => api.get(`/models/${encodeURIComponent(name)}`)

// 获取型号趋势
export const getModelTrend = (name, days = 30) =>
  api.get(`/models/${encodeURIComponent(name)}/trend`, { params: { days } })

// 获取记录列表
export const getRecords = (params) => api.get('/records/', { params })

// 获取单条记录
export const getRecord = (id) => api.get(`/records/${id}`)

// 获取统计数据
export const getStats = () => api.get('/stats/')

// 获取品牌统计
export const getBrandStats = () => api.get('/stats/brands')

// 获取成色统计
export const getConditionStats = () => api.get('/stats/conditions')

// 获取完整产品库
export const getRacketDatabase = () => api.get('/database/')

// 获取品牌列表
export const getBrands = () => api.get('/database/brands')

export default api
