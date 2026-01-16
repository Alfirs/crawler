import { messageStore } from './message-store.service';
import { logger } from '@/config/logger.config';

interface ProcessedEvent {
  eventId: string;
  dedupKey: string;
  processedAt: string;
  resultRef?: string;
}

export class DeduplicationService {
  async isProcessed(dedupKey: string): Promise<boolean> {
    try {
      return await messageStore.isProcessed(dedupKey);
    } catch (error) {
      logger.error({ err: error }, 'DeduplicationService.isProcessed error');
      // On error, allow processing to avoid blocking
      return false;
    }
  }

  async markProcessed(eventId: string, dedupKey: string, resultRef?: string): Promise<void> {
    try {
      await messageStore.markProcessed(eventId, dedupKey, resultRef);
    } catch (error) {
      logger.error({ err: error }, 'DeduplicationService.markProcessed error');
      // Don't throw - logging is sufficient
    }
  }

  // Generate dedup key for inbound message
  generateMessageDedupKey(channel: string, accountId: string, externalMessageRefId: string): string {
    return `msg:${channel}:${accountId}:${externalMessageRefId}`;
  }

  // Generate dedup key for status update
  generateStatusDedupKey(
    channel: string,
    accountId: string,
    externalMessageRefId: string,
    status: string,
    occurredAt: string
  ): string {
    return `status:${channel}:${accountId}:${externalMessageRefId}:${status}:${occurredAt}`;
  }
}
