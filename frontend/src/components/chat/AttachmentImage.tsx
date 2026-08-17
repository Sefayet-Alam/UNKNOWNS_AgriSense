"use client";

import { useEffect, useState } from "react";

import { apiAttachmentContent } from "@/lib/api";

/**
 * Renders a user-uploaded image by fetching it with the Bearer token (an
 * <img src> can't send auth headers) and showing it via an object URL.
 */
export function AttachmentImage({ id }: { id: number }) {
  const [url, setUrl] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    let objectUrl = "";
    (async () => {
      try {
        const res = await apiAttachmentContent(id);
        if (!res.ok) return;
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setUrl(objectUrl);
      } catch {
        /* ignore — the bubble simply shows text only */
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id]);

  if (!url) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt="attached leaf photo"
      className="max-h-56 w-auto rounded-[1.1rem] border border-jute-300/60 object-cover shadow-card"
    />
  );
}
