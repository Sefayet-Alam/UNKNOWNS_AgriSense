"use client";

import { ImagePlus, Loader2, Mic, Send, X } from "lucide-react";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

import { apiUpload } from "@/lib/api";

export interface ComposerHandle {
  setValue: (v: string) => void;
  focus: () => void;
}

interface Props {
  onSend: (message: string, attachmentIds?: number[]) => void;
  disabled?: boolean;
}

/**
 * Sticky composer. Enter sends, Shift+Enter inserts a newline. Auto-grows.
 * Supports a leaf-photo attachment (disease detection) and a voice note
 * (transcribed to text for low-literacy accessibility).
 */
export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { onSend, disabled },
  ref,
) {
  const [value, setValue] = useState("");
  const [imageId, setImageId] = useState<number | null>(null);
  const [imageName, setImageName] = useState<string>("");
  const [busy, setBusy] = useState<"image" | "audio" | null>(null);
  const [note, setNote] = useState<string>("");
  const taRef = useRef<HTMLTextAreaElement>(null);
  const imgInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);

  useImperativeHandle(ref, () => ({
    setValue: (v: string) => {
      setValue(v);
      requestAnimationFrame(() => taRef.current?.focus());
    },
    focus: () => taRef.current?.focus(),
  }));

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [value]);

  const onPickImage = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setNote("");
    setBusy("image");
    try {
      const res = await apiUpload(file);
      setImageId(res.id);
      setImageName(file.name);
    } catch (err) {
      setNote((err as Error).message || "Image upload failed");
    } finally {
      setBusy(null);
    }
  };

  const onPickAudio = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setNote("");
    setBusy("audio");
    try {
      const res = await apiUpload(file);
      if (res.transcript) {
        setValue((v) => (v ? `${v} ${res.transcript}` : res.transcript!));
        requestAnimationFrame(() => taRef.current?.focus());
      }
      if (res.warning) setNote(res.warning);
      else if (!res.transcript) setNote("No speech detected in the voice note.");
    } catch (err) {
      setNote((err as Error).message || "Voice upload failed");
    } finally {
      setBusy(null);
    }
  };

  const submit = () => {
    const trimmed = value.trim();
    // A photo can be sent with no typed text — use a default ask.
    const outgoing =
      trimmed || (imageId != null ? "Please check this leaf photo for disease." : "");
    if (!outgoing || disabled) return;
    onSend(outgoing, imageId != null ? [imageId] : undefined);
    setValue("");
    setImageId(null);
    setImageName("");
    setNote("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const canSend =
    !disabled && busy === null && (value.trim().length > 0 || imageId != null);

  return (
    <div className="sticky bottom-0 border-t border-jute-300/55 bg-paper-50/92 px-3 py-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] backdrop-blur sm:px-4 sm:py-3 sm:pb-3">
      <input
        ref={imgInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={onPickImage}
      />
      <input
        ref={audioInputRef}
        type="file"
        accept="audio/*"
        capture
        className="hidden"
        onChange={onPickAudio}
      />

      {(imageId != null || note) && (
        <div className="mx-auto mb-1.5 flex w-full max-w-3xl flex-wrap items-center gap-2 text-xs">
          {imageId != null && (
            <span className="inline-flex items-center gap-1 rounded-full bg-field-700/10 px-2.5 py-1 text-field-900">
              <ImagePlus size={13} />
              {imageName || "leaf photo"}
              <button
                type="button"
                aria-label="Remove photo"
                onClick={() => {
                  setImageId(null);
                  setImageName("");
                }}
              >
                <X size={13} />
              </button>
            </span>
          )}
          {note && <span className="text-text-muted">{note}</span>}
        </div>
      )}

      <div className="mx-auto flex w-full max-w-3xl items-end gap-2">
        <button
          type="button"
          onClick={() => imgInputRef.current?.click()}
          disabled={disabled || busy !== null}
          aria-label="Attach leaf photo"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-jute-300/70 bg-surface text-field-700 transition hover:bg-field-700/10 disabled:opacity-50"
        >
          {busy === "image" ? <Loader2 size={18} className="animate-spin" /> : <ImagePlus size={18} strokeWidth={1.75} />}
        </button>
        <button
          type="button"
          onClick={() => audioInputRef.current?.click()}
          disabled={disabled || busy !== null}
          aria-label="Attach voice note"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-jute-300/70 bg-surface text-field-700 transition hover:bg-field-700/10 disabled:opacity-50"
        >
          {busy === "audio" ? <Loader2 size={18} className="animate-spin" /> : <Mic size={18} strokeWidth={1.75} />}
        </button>
        <div className="flex-1 rounded-[1.35rem] border border-jute-300/70 bg-surface shadow-card transition duration-300 focus-within:-translate-y-0.5 focus-within:border-clay-400/70 focus-within:shadow-[0_18px_35px_-28px_rgba(23,38,28,0.55)]">
          <textarea
            ref={taRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Ask about your crops, soil, or plan…"
            className="max-h-36 min-h-11 w-full resize-none bg-transparent px-4 py-3 text-base text-text-primary outline-none placeholder:text-text-muted sm:max-h-52 sm:text-sm"
          />
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          aria-label="Send message"
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white shadow-card transition duration-200 ${
            canSend
              ? "bg-field-700 hover:-translate-y-1 hover:scale-105 hover:bg-field-900 hover:shadow-lift active:translate-y-0 active:scale-95"
              : "cursor-not-allowed bg-primary-200"
          }`}
        >
          <Send size={18} strokeWidth={1.75} />
        </button>
      </div>
      <p className="mx-auto mt-1.5 hidden max-w-3xl text-center text-xs text-text-muted sm:block">
        Enter to send · Shift+Enter for a new line · 📷 leaf photo · 🎤 voice note
      </p>
    </div>
  );
});
