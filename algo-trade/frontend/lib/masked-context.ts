"use client";

import { createContext, useContext } from "react";
import type { ToastData } from "@/components/ui/toast";

interface MaskedContextValue {
  masked: boolean;
  addToast: (t: Omit<ToastData, "id">) => void;
}

export const MaskedContext = createContext<MaskedContextValue>({
  masked: true,
  addToast: () => {},
});

export function useMasked() {
  return useContext(MaskedContext);
}
