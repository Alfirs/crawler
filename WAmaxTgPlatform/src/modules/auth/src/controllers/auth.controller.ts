import { Router, Request, Response } from 'express';
import { TokenService } from '../services/token.service';
import { verifySocketAuth } from '../middleware/auth.middleware';
import { config } from '@/config/env.config';

export class AuthController {
  private router: Router;

  constructor(private readonly tokenService: TokenService = new TokenService()) {
    this.router = Router();
    this.setupRoutes();
  }

  private setupRoutes(): void {
    this.router.post('/token', this.issueToken.bind(this));
    this.router.post('/verify', this.verifyToken.bind(this));
  }

  private issueToken(req: Request, res: Response): void {
    const apiKey = req.body?.apiKey as string | undefined;

    if (!apiKey) {
      res.status(400).json({
        error: {
          code: 'MISSING_API_KEY',
          message: 'apiKey is required',
        },
      });
      return;
    }

    if (apiKey !== config.API_KEY_SECRET) {
      res.status(401).json({
        error: {
          code: 'INVALID_API_KEY',
          message: 'Invalid API key',
        },
      });
      return;
    }

    const { token, expiresIn } = this.tokenService.issueToken('api-key');
    res.json({ token, expiresIn });
  }

  private verifyToken(req: Request, res: Response): void {
    const apiKey = (req.header('x-api-key') || req.body?.apiKey) as string | undefined;
    const tokenHeader = req.header('authorization') as string | undefined;
    const tokenBody = req.body?.token as string | undefined;

    const result = verifySocketAuth({
      apiKey: apiKey || undefined,
      token: tokenBody || undefined,
      authorization: tokenHeader,
    });
    if (result.ok) {
      res.json({ valid: true, subject: result.subject });
      return;
    }

    res.status(401).json({
      error: {
        code: 'UNAUTHORIZED',
        message: 'Invalid or missing credentials',
      },
    });
  }

  get routerInstance(): Router {
    return this.router;
  }
}

export const authRouter = new AuthController().routerInstance;
