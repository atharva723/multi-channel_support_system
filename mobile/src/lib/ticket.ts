import { type Ticket } from '../api/client';

export interface TicketDisplay {
  /** Short heading — the email subject, or the author for chat channels. */
  heading: string;
  /** Secondary line — author for email, or the message body for chat. */
  subheading: string;
  /** The main message body (subject stripped for email). */
  body: string;
}

/**
 * Normalize a ticket for display. Email tickets arrive as "SUBJECT\n\nBODY"
 * (from the Gmail poller), so we split them; chat channels use author + content.
 */
export function ticketDisplay(ticket: Ticket): TicketDisplay {
  const isEmail = ticket.channel?.toLowerCase() === 'email';
  if (isEmail) {
    const [firstLine, ...rest] = ticket.content.split('\n');
    const body = rest.join('\n').trim();
    return {
      heading: firstLine.trim() || '(no subject)',
      subheading: ticket.author_name,
      body: body || firstLine.trim(),
    };
  }
  return {
    heading: ticket.author_name,
    subheading: '',
    body: ticket.content,
  };
}
