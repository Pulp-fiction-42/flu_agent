/**
 * 认证工具模块
 * 处理 JWT token 的存储、获取，以及 Guest 自动登录
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const TOKEN_KEY = 'bioagent_token';
const USER_KEY = 'bioagent_user';

export interface AuthUser {
  user_id: string;
  username: string;
  token: string;
}

/** 获取当前存储的 token */
export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** 获取当前用户信息 */
export function getUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** 保存认证信息 */
function saveAuth(user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, user.token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** 清除认证信息 */
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/** 注册新用户 */
async function register(username: string, password: string): Promise<{ user_id: string; username: string }> {
  const res = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Registration failed');
  }
  return res.json();
}

/** 登录 */
async function login(username: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Login failed');
  }
  const data = await res.json();
  return {
    user_id: data.user_id,
    username: data.username,
    token: data.token,
  };
}

/**
 * 自动 Guest 登录
 * 1. 如果 localStorage 中已有有效 token，直接使用
 * 2. 否则注册一个随机 Guest 用户并登录
 */
export async function ensureAuthenticated(): Promise<AuthUser> {
  const existing = getUser();
  if (existing?.token) {
    // 简单验证 token 是否还有效（调用健康检查）
    try {
      const res = await fetch(`${API_BASE_URL}/conversations`, {
        headers: { 'Authorization': `Bearer ${existing.token}` }
      });
      if (res.ok) {
        return existing;
      }
      // 如果 401，清空并重新注册
      if (res.status === 401) {
        clearAuth();
      }
    } catch (e) {
      // 网络错误忽略，继续返回缓存
    }
  }

  // 生成随机 Guest 用户名
  const guestId = `guest_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const password = `pass_${guestId}`;

  try {
    // 注册
    await register(guestId, password);
  } catch (e: any) {
    // 如果用户名已存在，忽略（理论上随机名不会冲突）
    if (!e.message?.includes('已存在')) throw e;
  }

  // 登录
  const user = await login(guestId, password);
  saveAuth(user);
  return user;
}
