import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import EventSource from 'react-native-sse';

import { type Ticket } from '../api/client';
import { apiUrl } from '../lib/config';
import { hapticWarning } from '../lib/haptics';
import { useAuthStore } from './useAuthStore';
import { useRealtimeStore } from './useRealtimeStore';
import { ticketKeys } from './useTickets';

/** Custom SSE event names emitted by the backend stream. */
type SentinelEvent = 'escalation' | 'ticket_update';

/**
 * Subscribe to the backend SSE stream for the current account.
 *
 * Mounted ONCE app-wide (in the tab layout) so realtime updates land on every
 * screen, not just the Desk. EventSource can't send Authorization headers, so
 * the session token is passed as a query param (the backend accepts either).
 *
 * Each event carries the full ticket payload, so we patch the React Query cache
 * directly (instant, precise) and invalidate as a fallback. Escalations pulse a
 * haptic + the realtime store so the Desk can raise its banner.
 */
export function useEscalationStream() {
  const token = useAuthStore((s) => s.token);
  const qc = useQueryClient();
  const pulseEscalation = useRealtimeStore((s) => s.pulseEscalation);
  const setStreamStatus = useRealtimeStore((s) => s.setStreamStatus);

  useEffect(() => {
    if (!token) return;

    const url = `${apiUrl('/support/stream')}?token=${encodeURIComponent(token)}`;
    const es = new EventSource<SentinelEvent>(url, {
      headers: { Authorization: `Bearer ${token}` },
      // Long-lived stream; the server sends keepalives every 15s.
      pollingInterval: 0,
    });

    /** Merge an incoming ticket into every cached list + its detail entry. */
    const applyTicket = (raw: string | undefined) => {
      let ticket: Ticket | null = null;
      if (raw) {
        try {
          ticket = JSON.parse(raw) as Ticket;
        } catch {
          ticket = null;
        }
      }
      if (ticket) {
        const incoming = ticket;
        qc.setQueryData(ticketKeys.detail(incoming.id), incoming);
        qc.setQueriesData<Ticket[]>({ queryKey: ticketKeys.all }, (list) => {
          if (!Array.isArray(list)) return list;
          const idx = list.findIndex((t) => t.id === incoming.id);
          if (idx === -1) return [incoming, ...list];
          const next = list.slice();
          next[idx] = incoming;
          return next;
        });
      }
      // Fallback so any list not held in cache still reconciles.
      qc.invalidateQueries({ queryKey: ticketKeys.all });
    };

    es.addEventListener('open', () => setStreamStatus('live'));

    es.addEventListener('escalation', (event) => {
      hapticWarning();
      applyTicket((event as { data?: string }).data);
      pulseEscalation();
    });

    es.addEventListener('ticket_update', (event) => {
      applyTicket((event as { data?: string }).data);
    });

    es.addEventListener('error', () => setStreamStatus('error'));

    return () => {
      es.removeAllEventListeners();
      es.close();
    };
  }, [token, qc, pulseEscalation, setStreamStatus]);
}
