import { Request, Response } from 'express';
import { OutboundMessageSendRequest } from '../dto/outbound-message-send.dto';
import { OutboundSendResponse, ErrorResponse } from '../dto/response.dto';
import { OutboundMessageService } from '../services/outbound-message.service';
import { validateSchema } from '../middleware/validation.middleware';
import { outboundMessageSendSchema } from '../validate/outbound-message.schema';
import { logger } from '@/config/logger.config';

export class OutboundMessageController {
  constructor(private readonly outboundService: OutboundMessageService = new OutboundMessageService()) {}

  sendMessage = [
    validateSchema(outboundMessageSendSchema),
    async (req: Request, res: Response): Promise<void> => {
    try {
      const idempotencyKey = req.headers['idempotency-key'] as string;

      if (!idempotencyKey) {
        const error: ErrorResponse = {
          error: {
            code: 'MISSING_IDEMPOTENCY_KEY',
            message: 'Idempotency-Key header is required'
          }
        };
        res.status(400).json(error);
        return;
      }

      const request: OutboundMessageSendRequest = req.body;

      // Basic validation
      if (request.channel !== 'WHATSAPP') {
        const error: ErrorResponse = {
          error: {
            code: 'UNSUPPORTED_CHANNEL',
            message: 'Only WHATSAPP channel is supported'
          }
        };
        res.status(422).json(error);
        return;
      }

      const result = await this.outboundService.sendMessage(request, idempotencyKey);

      const response: OutboundSendResponse = {
        deliveryRequestId: result.deliveryRequestId,
        status: result.status
      };

      res.status(202).json(response);
    } catch (error: any) {
      logger.error({ err: error }, 'OutboundMessageController.sendMessage error');

      if (error.code === 'IDEMPOTENCY_CONFLICT') {
        const response: ErrorResponse = {
          error: {
            code: 'IDEMPOTENCY_CONFLICT',
            message: 'Request with this Idempotency-Key already processed'
          }
        };
        res.status(409).json(response);
        return;
      }

      if (error.code === 'CHANNEL_ACCOUNT_NOT_FOUND') {
        const response: ErrorResponse = {
          error: {
            code: 'CHANNEL_ACCOUNT_NOT_FOUND',
            message: 'Channel account not found or not connected'
          }
        };
        res.status(404).json(response);
        return;
      }

      if (error.code === 'UNSUPPORTED_MESSAGE_TYPE') {
        const response: ErrorResponse = {
          error: {
            code: 'UNSUPPORTED_MESSAGE_TYPE',
            message: 'Message type not supported by channel'
          }
        };
        res.status(422).json(response);
        return;
      }

      const response: ErrorResponse = {
        error: {
          code: 'INTERNAL_ERROR',
          message: 'Internal server error'
        }
      };
      res.status(500).json(response);
    }
  }];
}
