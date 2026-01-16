import { Request, Response } from 'express';
import { InboundWebhookService } from '../services/inbound-webhook.service';
import { ErrorResponse } from '../dto/response.dto';
import { logger } from '@/config/logger.config';

export class InboundWebhookController {
  constructor(private readonly webhookService: InboundWebhookService = new InboundWebhookService()) {}

  handleWebhook = async (req: Request, res: Response): Promise<void> => {
    try {
      // Auth TBD: shared secret signature header OR internal allowlist
      // For now, accept all requests (should be secured by network/firewall)

      const eventName = req.body?.event as string | undefined;
      const isStatus = this.webhookService.isStatusEvent(eventName) || Boolean(req.body?.status);

      if (isStatus) {
        await this.webhookService.processStatus(req.body);
      } else {
        await this.webhookService.processWebhook(req.body);
      }

      res.status(200).send('OK');
    } catch (error: any) {
      logger.error({ err: error }, 'InboundWebhookController.handleWebhook error');

      if (error.code === 'INVALID_SIGNATURE') {
        const response: ErrorResponse = {
          error: {
            code: 'INVALID_SIGNATURE',
            message: 'Invalid webhook signature'
          }
        };
        res.status(401).json(response);
        return;
      }

      if (error.code === 'INVALID_PROVIDER_PAYLOAD') {
        const response: ErrorResponse = {
          error: {
            code: 'INVALID_PROVIDER_PAYLOAD',
            message: 'Invalid provider payload format'
          }
        };
        res.status(400).json(response);
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
  };

  handleStatus = async (req: Request, res: Response): Promise<void> => {
    try {
      // Auth TBD: shared secret signature header OR internal allowlist

      await this.webhookService.processStatus(req.body);

      res.status(200).send('OK');
    } catch (error: any) {
      logger.error({ err: error }, 'InboundWebhookController.handleStatus error');

      if (error.code === 'INVALID_SIGNATURE') {
        const response: ErrorResponse = {
          error: {
            code: 'INVALID_SIGNATURE',
            message: 'Invalid webhook signature'
          }
        };
        res.status(401).json(response);
        return;
      }

      if (error.code === 'INVALID_PROVIDER_PAYLOAD') {
        const response: ErrorResponse = {
          error: {
            code: 'INVALID_PROVIDER_PAYLOAD',
            message: 'Invalid provider payload format'
          }
        };
        res.status(400).json(response);
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
  };
}
