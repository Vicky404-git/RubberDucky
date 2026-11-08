import { useEffect } from "react";
import { useAppStore } from "../stores/appStore";

export function useBridge(): void {
  const bootstrap = useAppStore((state) => state.bootstrap);
  const connectEvents = useAppStore((state) => state.connectEvents);
  const disconnectEvents = useAppStore((state) => state.disconnectEvents);

  useEffect(() => {
    void bootstrap();
    connectEvents();
    return () => disconnectEvents();
  }, [bootstrap, connectEvents, disconnectEvents]);
}
