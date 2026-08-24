import { api } from "./client";
import type { LoginRequest, TokenResponse } from "@/types/api";

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/api/auth/login", payload);
  return data;
}
