"use client";

// ConfirmDialog — a ready-made confirmation modal for destructive actions
// (delete project, archive, etc.). Renders a Dialog with confirm/cancel and
// shows a loading state while the action is in flight.

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter, DialogHeader } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/skeleton";

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description?: string;
  confirmLabel?: string;
  variant?: "default" | "destructive";
  loading?: boolean;
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  variant = "destructive",
  loading = false,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={loading ? () => {} : onClose} labelledBy="dialog-title">
      <DialogHeader title={title} description={description} />
      <DialogFooter>
        <Button variant="outline" onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button variant={variant} onClick={() => void onConfirm()} disabled={loading}>
          {loading ? <Spinner /> : confirmLabel}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
