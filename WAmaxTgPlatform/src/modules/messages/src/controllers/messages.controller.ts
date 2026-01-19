import { Router, Request, Response } from 'express';
import { Conversation } from '../dto/conversation.dto';
import { Message } from '../dto/message.dto';
import { MessageQueryService } from '../services/message-query.service';
import { logger } from '@/config/logger.config';

export class MessagesController {
  private router: Router;

  constructor(private readonly queryService: MessageQueryService = new MessageQueryService()) {
    this.router = Router();
    this.setupRoutes();
  }

  private setupRoutes(): void {
    // Get conversations for account
    this.router.get('/conversations', this.getConversations.bind(this));

    // Get messages in conversation
    this.router.get('/conversations/:conversationId/messages', this.getMessages.bind(this));

    // Get single message
    this.router.get('/messages/:messageId', this.getMessage.bind(this));
  }

  private async getConversations(req: Request, res: Response): Promise<void> {
    try {
      const { accountId, channel, limit = 50, offset = 0 } = req.query;

      if (!accountId || !channel) {
        res.status(400).json({
          error: {
            code: 'MISSING_PARAMETERS',
            message: 'accountId and channel are required'
          }
        });
        return;
      }

      const conversations = await this.queryService.getConversations(
        accountId as string,
        channel as string,
        parseInt(limit as string),
        parseInt(offset as string)
      );

      res.json({
        conversations,
        pagination: {
          limit: parseInt(limit as string),
          offset: parseInt(offset as string)
        }
      });
    } catch (error) {
      logger.error({ err: error }, 'MessagesController.getConversations error');
      res.status(500).json({
        error: {
          code: 'INTERNAL_ERROR',
          message: 'Failed to fetch conversations'
        }
      });
    }
  }

  private async getMessages(req: Request, res: Response): Promise<void> {
    try {
      const { conversationId } = req.params;
      const { limit = 100, offset = 0, direction } = req.query;

      const messages = await this.queryService.getMessages(
        conversationId,
        {
          limit: parseInt(limit as string),
          offset: parseInt(offset as string),
          direction: direction as 'INBOUND' | 'OUTBOUND' | undefined
        }
      );

      res.json({
        messages,
        pagination: {
          limit: parseInt(limit as string),
          offset: parseInt(offset as string)
        }
      });
    } catch (error) {
      logger.error({ err: error }, 'MessagesController.getMessages error');
      res.status(500).json({
        error: {
          code: 'INTERNAL_ERROR',
          message: 'Failed to fetch messages'
        }
      });
    }
  }

  private async getMessage(req: Request, res: Response): Promise<void> {
    try {
      const { messageId } = req.params;

      const message = await this.queryService.getMessage(messageId);

      if (!message) {
        res.status(404).json({
          error: {
            code: 'MESSAGE_NOT_FOUND',
            message: 'Message not found'
          }
        });
        return;
      }

      res.json({ message });
    } catch (error) {
      logger.error({ err: error }, 'MessagesController.getMessage error');
      res.status(500).json({
        error: {
          code: 'INTERNAL_ERROR',
          message: 'Failed to fetch message'
        }
      });
    }
  }

  get routerInstance(): Router {
    return this.router;
  }
}

// Export router instance
export const messagesRouter = new MessagesController().routerInstance;
