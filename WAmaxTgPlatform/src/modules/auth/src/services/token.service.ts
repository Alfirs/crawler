import jwt from 'jsonwebtoken';
import { config } from '@/config/env.config';

export class TokenService {
  issueToken(subject: string): { token: string; expiresIn: number } {
    const expiresIn = config.AUTH_TOKEN_TTL_SECONDS;
    const token = jwt.sign({ sub: subject }, config.JWT_SECRET, {
      expiresIn,
    });

    return { token, expiresIn };
  }

  verifyToken(token: string): jwt.JwtPayload {
    return jwt.verify(token, config.JWT_SECRET) as jwt.JwtPayload;
  }
}
