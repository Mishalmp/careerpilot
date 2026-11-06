"use client";

import { useEffect, useRef } from "react";

/** A modal built on the native <dialog>: focus trap, Escape to close and backdrop come for free. */
export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="modal-title"
      className="m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg rounded-lg border border-border-subtle bg-popover p-0 text-foreground shadow-float backdrop:bg-overlay"
    >
      {open && (
        <div className="space-y-4 p-5">
          <h2 id="modal-title" className="text-lg font-semibold tracking-tight">
            {title}
          </h2>
          {children}
        </div>
      )}
    </dialog>
  );
}
