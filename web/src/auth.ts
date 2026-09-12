// Auth-контекст отдельно от main (без циклических импортов)
import { createContext, useContext } from "react";

export interface AuthUser {
  role: string;
  full_name: string;
}

export const AuthCtx = createContext<{ user: AuthUser | null; logout: () => void }>({
  user: null,
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthCtx);
}
