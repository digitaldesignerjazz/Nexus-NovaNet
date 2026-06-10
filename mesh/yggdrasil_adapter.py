#!/usr/bin/env python3
"""
Nexus NovaNet - Yggdrasil Adapter

Dieses Modul stellt den Yggdrasil-Adapter für den Mesh Communication Layer von Nexus dar.

Yggdrasil wird als dezentrales, selbstheilendes Overlay-Netzwerk genutzt,
um Agenten-Schwärme sicher, resilient und standortunabhängig miteinander
verbindet.

Architektur-Position:
  Mesh Communication Layer (Abstraktion)
         ↓
  Yggdrasil Adapter (primär)
         ↓
  Yggdrasil IPv6 Overlay Network

Der Adapter übersetzt die abstrakten Mesh-Operationen in konkrete
Yggdrasil-kompatible Kommunikation (IPv6 + Ende-zu-Ende-Verschlüsselung).

Zukünftige Erweiterungen:
- Native Integration via yggdrasil Admin API / TUN
- Unterstützung für dynamische Peering
- Metriken für die Selbstverbesserungsschleife (Route Quality, Latency, Stability)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Callable
import socket
import threading
import time


class YggdrasilAdapterError(Exception):
    """Basis-Exception für alle Yggdrasil-Adapter-Fehler."""
    pass


class YggdrasilAdapter(ABC):
    """
    Abstrakter Adapter für die Integration von Yggdrasil in Nexus NovaNet.

    Jeder Nexus-Agent, der über das Mesh kommunizieren möchte, nutzt
    eine Instanz dieses Adapters (oder eine konkrete Implementierung).

    Der Adapter ist bewusst leichtgewichtig und asynchron-fähig,
    damit er gut in Agenten-Schwärme und die Selbstverbesserungsschleife passt.
    """

    def __init__(self, local_ygg_ipv6: str, listen_port: int = 8443):
        """
        Initialisiert den Adapter.

        Args:
            local_ygg_ipv6: Die stabile Yggdrasil-IPv6-Adresse dieses Nodes
                              (z.B. '0200:0:0:0:0:0:0:1' oder echte aus yggdrasilctl)
            listen_port: Port, auf dem auf eingehende Verbindungen gewartet wird
        """
        self.local_ygg_ipv6 = local_ygg_ipv6
        self.listen_port = listen_port
        self._running = False
        self._peers: Dict[str, dict] = {}          # ygg_ipv6 -> peer_info
        self._message_handlers: List[Callable] = []
        self._lock = threading.Lock()

    @abstractmethod
    def connect_to_peer(self, peer_ygg_ipv6: str, port: int = 8443) -> bool:
        """
        Stellt eine Verbindung zu einem anderen Yggdrasil-Node her.

        In der realen Implementierung:
        - Öffnet einen TCP-Socket auf die Yggdrasil-IPv6
        - Führt ggf. TLS-Handshake durch (Yggdrasil ist bereits E2E-verschlüsselt)
        - Registriert den Peer im internen Routing
        """
        pass

    @abstractmethod
    def send_message(self, target_ygg_ipv6: str, payload: bytes, 
                     message_type: str = "agent_message") -> bool:
        """
        Sendet eine Nachricht an einen anderen Agenten über Yggdrasil.

        Die Nachricht wird Ende-zu-Ende verschlüsselt (durch Yggdrasil).
        """
        pass

    @abstractmethod
    def broadcast(self, payload: bytes, message_type: str = "swarm_broadcast") -> int:
        """
        Sendet eine Nachricht an alle bekannten Peers (oder einen Sub-Schwarm).

        Wird z.B. für Agenten-Schwarm-Koordination oder Heartbeats genutzt.
        """
        pass

    def register_message_handler(self, handler: Callable[[str, bytes, dict], None]):
        """
        Registriert einen Callback, der bei eingehenden Nachrichten aufgerufen wird.

        Handler-Signatur: handler(sender_ygg_ipv6: str, payload: bytes, metadata: dict)
        """
        with self._lock:
            self._message_handlers.append(handler)

    def start_listener(self):
        """
        Startet den Listener-Thread für eingehende Verbindungen.

        In der Praxis würde hier ein Socket auf [::]:port gebunden werden,
        das über das Yggdrasil-Interface läuft.
        """
        self._running = True
        listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        listener_thread.start()
        print(f"[YggdrasilAdapter] Listener gestartet auf [{self.local_ygg_ipv6}]:{self.listen_port}")

    def _listen_loop(self):
        """Interner Listener-Loop (Platzhalter für echte Socket-Implementierung)."""
        # TODO: Echte Implementierung mit socket.AF_INET6 + Yggdrasil-Interface
        while self._running:
            time.sleep(1)  # Platzhalter

    def stop(self):
        self._running = False
        print("[YggdrasilAdapter] Adapter gestoppt.")

    def get_connected_peers(self) -> List[str]:
        """Gibt eine Liste aller aktuell verbundenen Yggdrasil-Peers zurück."""
        with self._lock:
            return list(self._peers.keys())

    def get_adapter_status(self) -> dict:
        """
        Liefert Status-Informationen für die Reflexions-Agenten
        der Selbstverbesserungsschleife.
        """
        return {
            "local_address": self.local_ygg_ipv6,
            "connected_peers": len(self._peers),
            "running": self._running,
            "listen_port": self.listen_port,
            "timestamp": time.time()
        }


class MockYggdrasilAdapter(YggdrasilAdapter):
    """
    Mock-Implementierung für Tests, Prototyping und die frühe Entwicklungsphase.

    Simuliert Yggdrasil-Verhalten ohne echten Daemon.
    Sehr nützlich für die ersten Agenten-Schwarm-Experimente.
    """

    def connect_to_peer(self, peer_ygg_ipv6: str, port: int = 8443) -> bool:
        with self._lock:
            if peer_ygg_ipv6 not in self._peers:
                self._peers[peer_ygg_ipv6] = {
                    "connected_at": time.time(),
                    "last_seen": time.time(),
                    "port": port
                }
                print(f"[MockYggdrasil] Verbunden mit Peer: {peer_ygg_ipv6}")
                return True
            return False

    def send_message(self, target_ygg_ipv6: str, payload: bytes, 
                     message_type: str = "agent_message") -> bool:
        if target_ygg_ipv6 not in self._peers:
            print(f"[MockYggdrasil] WARNUNG: Unbekannter Peer {target_ygg_ipv6}")
            return False

        print(f"[MockYggdrasil] Sende {message_type} an {target_ygg_ipv6} ({len(payload)} Bytes)")
        # Simuliere Empfang beim Ziel (für Tests)
        for handler in self._message_handlers:
            try:
                handler(target_ygg_ipv6, payload, {"type": message_type, "mock": True})
            except Exception as e:
                print(f"[MockYggdrasil] Handler-Fehler: {e}")
        return True

    def broadcast(self, payload: bytes, message_type: str = "swarm_broadcast") -> int:
        sent = 0
        for peer in list(self._peers.keys()):
            if self.send_message(peer, payload, message_type):
                sent += 1
        print(f"[MockYggdrasil] Broadcast an {sent} Peers gesendet.")
        return sent


# ============================================================
# Beispiel-Nutzung (kann später in Agenten-Code verschoben werden)
# ============================================================

if __name__ == "__main__":
    print("Nexus NovaNet - Yggdrasil Adapter Demo")
    print("=" * 50)

    adapter = MockYggdrasilAdapter("0200:0:0:0:0:0:0:42")
    adapter.start_listener()

    # Simuliere einen anderen Agenten
    adapter.connect_to_peer("0200:0:0:0:0:0:0:43")

    def on_message(sender, payload, meta):
        print(f"[Agent] Nachricht von {sender}: {payload.decode(errors='ignore')}")

    adapter.register_message_handler(on_message)

    adapter.send_message("0200:0:0:0:0:0:0:43", b"Hallo vom Nexus-Schwarm", "agent_hello")

    time.sleep(2)
    adapter.stop()
