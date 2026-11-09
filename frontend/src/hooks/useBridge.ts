import { useEffect } from "react";
import { useAppStore } from "../stores/appStore";

const DAEMON_STATUS_POLL_INTERVAL_MS = 3_000;

export function useBridge(): void {
  const bootstrap = useAppStore((state) => state.bootstrap);
  const connectEvents = useAppStore((state) => state.connectEvents);
  const disconnectEvents = useAppStore((state) => state.disconnectEvents);
  const refreshStatus = useAppStore((state) => state.refreshStatus);

  useEffect(() => {
    void bootstrap();
    connectEvents();

    // The daemon does not currently emit WebSocket events when it starts/stops.
    // Poll only status so this does not reset sessions or other frontend state.
    let statusRequestInFlight = false;
    const refreshDaemonStatus = () => {
      if (statusRequestInFlight) return;
      statusRequestInFlight = true;
      void refreshStatus().finally(() => {
        statusRequestInFlight = false;
      });
    };

    const statusTimer = window.setInterval(
      refreshDaemonStatus,
      DAEMON_STATUS_POLL_INTERVAL_MS,
    );

    return () => {
      window.clearInterval(statusTimer);
      disconnectEvents();
    };
  }, [bootstrap, connectEvents, disconnectEvents, refreshStatus]);
}
