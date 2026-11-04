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
      className="m-auto w-full max-w-lg rounded-lg border border-black/15 bg-background p-0 text-foreground backdrop:bg-black/40 dark:border-white/20"
    >
      {open && (
        <div className="space-y-4 p-5">
          <h2 id="modal-title" className="text-lg font-semibold">
            {title}
          </h2>
          {children}
        </div>
      )}
    </dialog>
  );
}
