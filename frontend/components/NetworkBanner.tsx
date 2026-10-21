"use client";

import { useEffect, useState } from "react";

export function NetworkBanner() {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  if (online) return null;
  return (
    <div role="status" className="sticky top-0 z-40 bg-surface px-4 py-2 text-center text-caption text-text">
      Нет интернета. Разговор сохранён — продолжите, когда связь вернётся.
    </div>
  );
}
