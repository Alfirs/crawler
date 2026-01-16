import { Request, Response } from 'express';
import { ChannelConnectRequest, ChannelDisconnectRequest, ChannelHealthQuery } from '../dto/channel.dto';
import { ChannelConnectResponse, ChannelDisconnectResponse, ChannelHealthResponse, ErrorResponse } from '../dto/response.dto';
import { ChannelService } from '../services/channel.service';
import { logger } from '@/config/logger.config';

export class ChannelController {
  constructor(private readonly channelService: ChannelService = new ChannelService()) {}

  connect = async (req: Request, res: Response): Promise<void> => {
    try {
      const request: ChannelConnectRequest = req.body;

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

      if (request.mode !== 'NEW') {
        const error: ErrorResponse = {
          error: {
            code: 'UNSUPPORTED_CONNECT_MODE',
            message: 'Only NEW connect mode is supported'
          }
        };
        res.status(422).json(error);
        return;
      }

      const result = await this.channelService.connect(request);

      const response: ChannelConnectResponse = {
        connectRequestId: result.connectRequestId,
        state: result.state
      };

      res.status(202).json(response);
    } catch (error: any) {
      logger.error({ err: error }, 'ChannelController.connect error');

      if (error.code === 'CHANNEL_ACCOUNT_NOT_FOUND') {
        const error: ErrorResponse = {
          error: {
            code: 'CHANNEL_ACCOUNT_NOT_FOUND',
            message: 'Channel account not found'
          }
        };
        res.status(404).json(error);
        return;
      }

      if (error.code === 'ALREADY_CONNECTED') {
        const error: ErrorResponse = {
          error: {
            code: 'ALREADY_CONNECTED',
            message: 'Channel already connected'
          }
        };
        res.status(409).json(error);
        return;
      }

      if (error.code === 'CONNECT_IN_PROGRESS') {
        const error: ErrorResponse = {
          error: {
            code: 'CONNECT_IN_PROGRESS',
            message: 'Connection already in progress'
          }
        };
        res.status(409).json(error);
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

  disconnect = async (req: Request, res: Response): Promise<void> => {
    try {
      const request: ChannelDisconnectRequest = req.body;

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

      await this.channelService.disconnect(request);

      const response: ChannelDisconnectResponse = {
        state: 'PENDING'
      };

      res.status(202).json(response);
    } catch (error: any) {
      logger.error({ err: error }, 'ChannelController.disconnect error');

      const response: ErrorResponse = {
        error: {
          code: 'INTERNAL_ERROR',
          message: 'Internal server error'
        }
      };
      res.status(500).json(response);
    }
  };

  health = async (req: Request, res: Response): Promise<void> => {
    try {
      const query: ChannelHealthQuery = {
        accountId: req.query.accountId as string
      };

      if (!query.accountId) {
        const error: ErrorResponse = {
          error: {
            code: 'MISSING_ACCOUNT_ID',
            message: 'accountId query parameter is required'
          }
        };
        res.status(400).json(error);
        return;
      }

      const health = await this.channelService.getHealth('WHATSAPP', query.accountId);

      const response: ChannelHealthResponse = {
        channel: 'WHATSAPP',
        accountId: query.accountId,
        connectionState: health.connectionState,
        lastSeenAt: health.lastSeenAt,
        details: health.details
      };

      res.status(200).json(response);
    } catch (error: any) {
      logger.error({ err: error }, 'ChannelController.health error');

      if (error.code === 'CHANNEL_ACCOUNT_NOT_FOUND') {
        const error: ErrorResponse = {
          error: {
            code: 'CHANNEL_ACCOUNT_NOT_FOUND',
            message: 'Channel account not found'
          }
        };
        res.status(404).json(error);
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
