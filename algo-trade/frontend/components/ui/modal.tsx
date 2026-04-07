"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function Modal({ open, onOpenChange, title, description, children, className }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2",
            "w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 shadow-2xl",
            "animate-in fade-in zoom-in-95 duration-150",
            className
          )}
        >
          <div className="flex items-start justify-between px-6 pt-5 pb-4 border-b border-zinc-800">
            <div>
              <Dialog.Title className="text-base font-semibold text-zinc-100">
                {title}
              </Dialog.Title>
              {description && (
                <Dialog.Description className="mt-1 text-sm text-zinc-400">
                  {description}
                </Dialog.Description>
              )}
            </div>
            <Dialog.Close className="ml-4 rounded-lg p-1 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors">
              <X className="w-4 h-4" />
              <span className="sr-only">Close</span>
            </Dialog.Close>
          </div>
          <div className="px-6 py-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
