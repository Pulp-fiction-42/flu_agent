import axios from 'axios';
import { getToken } from './auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

// 请求拦截器：自动附带 JWT token
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const uploadFiles = async (files: File[]) => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  const response = await apiClient.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getModels = async () => {
  const response = await apiClient.get('/models');
  return response.data;
};

export const getTools = async () => {
  const response = await apiClient.get('/tools');
  return response.data;
};

// Conversation APIs
export const listConversations = async () => {
  const response = await apiClient.get('/conversations');
  return response.data.conversations as ConversationSummary[];
};

export const createConversation = async (title?: string) => {
  const response = await apiClient.post('/conversations', { title });
  return response.data as ConversationSummary;
};

export const getConversation = async (id: string) => {
  const response = await apiClient.get(`/conversations/${id}`);
  return response.data as ConversationDetail;
};

export const deleteConversation = async (id: string) => {
  const response = await apiClient.delete(`/conversations/${id}`);
  return response.data;
};

export const updateConversationTitle = async (id: string, title: string) => {
  const response = await apiClient.patch(`/conversations/${id}/title`, { title });
  return response.data;
};

// Types
export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
  files: string[];
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  user_id: string;
  messages: ConversationMessage[];
}
