import { Request, Response, NextFunction } from 'express';
import { config } from '@/config/env.config';
import { TokenService } from '../services/token.service';

const tokenService = new TokenService();

function extractBearerToken(value?: string): string | undefined {
  if (!value) {
    return undefined;
  }
  const [type, token] = value.split(' ');
  if (type?.toLowerCase() === 'bearer' && token) {
    return token;
  }
  return undefined;
}

export function verifyAuth(token?: string, apiKey?: string): { ok: boolean; subject?: string } {
  if (apiKey && apiKey === config.API_KEY_SECRET) {
    return { ok: true, subject: 'api-key' };
  }

  if (token) {
    try {
      const payload = tokenService.verifyToken(token);
      return { ok: true, subject: payload.sub as string | undefined };
    } catch (error) {
      return { ok: false };
    }
  }

  return { ok: false };
}

export function authMiddleware(req: Request, res: Response, next: NextFunction): void {
  if (!config.AUTH_REQUIRED) {
    next();
    return;
  }

  const apiKey = req.header('x-api-key') || undefined;
  const token = extractBearerToken(req.header('authorization') || undefined);
  const result = verifyAuth(token, apiKey);

  if (result.ok) {
    next();
    return;
  }

  res.status(401).json({
    error: {
      code: 'UNAUTHORIZED',
      message: 'Authentication required',
    },
  });
}

export function verifySocketAuth(params: {
  apiKey?: string;
  token?: string;
  authorization?: string;
}): { ok: boolean; subject?: string } {
  const bearer = extractBearerToken(params.authorization);
  const token = params.token || bearer;
  return verifyAuth(token, params.apiKey);
}
