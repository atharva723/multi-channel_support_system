import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { TicketsApi, type Ticket, type TicketStatus } from '../api/client';
import { hapticError, hapticSuccess } from '../lib/haptics';

export const ticketKeys = {
  all: ['tickets'] as const,
  list: (status?: TicketStatus) => ['tickets', 'list', status ?? 'all'] as const,
  detail: (id: number) => ['tickets', 'detail', id] as const,
};

/** List tickets, optionally filtered by status. Escalations = PENDING criticals. */
export function useTickets(status?: TicketStatus) {
  return useQuery({
    queryKey: ticketKeys.list(status),
    queryFn: () => TicketsApi.list(status),
    staleTime: 10_000,
  });
}

export function useTicket(id: number) {
  return useQuery({
    queryKey: ticketKeys.detail(id),
    queryFn: () => TicketsApi.get(id),
    enabled: Number.isFinite(id),
  });
}

/** Approve / modify / dismiss a ticket. On approve/modify the backend sends. */
export function useUpdateTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      reply,
    }: {
      id: number;
      status: TicketStatus;
      reply?: string;
    }) => TicketsApi.update(id, { status, ai_draft_reply: reply }),
    onSuccess: async (updated: Ticket) => {
      hapticSuccess();
      qc.setQueryData(ticketKeys.detail(updated.id), updated);
      await qc.invalidateQueries({ queryKey: ticketKeys.all });
    },
    onError: () => {
      hapticError();
    },
  });
}
