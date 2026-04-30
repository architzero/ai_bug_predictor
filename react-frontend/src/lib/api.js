import apiClient from './api-client';

export const scanApi = {
  startScan: async (data) => {
    const response = await apiClient.post('/api/scan_repo', data);
    return response.data;
  },

  getScanProgress: async (scanId) => {
    const response = await apiClient.get(`/api/scan_progress/${scanId}`);
    return response.data;
  },

  getScanResults: async (scanId) => {
    const response = await apiClient.get(`/api/results/${scanId}`);
    return response.data;
  },

  getFileDetail: async (fileId) => {
    const response = await apiClient.get('/api/file', {
      params: { id: fileId },
    });
    return response.data;
  },

  getRecentScans: async () => {
    const response = await apiClient.get('/api/recent_scans');
    return response.data;
  },

  getRepos: async () => {
    const response = await apiClient.get('/api/repos');
    return response.data;
  },

  getModelPerformance: async () => {
    const response = await apiClient.get('/api/model_evaluation');
    return response.data;
  },
};

export default scanApi;
