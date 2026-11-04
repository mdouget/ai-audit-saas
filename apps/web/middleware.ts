import { NextRequest, NextResponse } from 'next/server';
import { auth0, authConfigured } from './lib/auth0';

export function middleware(request: NextRequest) {
  return authConfigured() ? auth0().middleware(request) : NextResponse.next();
}

export const config = { matcher: ['/auth/:path*', '/dashboard/:path*'], runtime: 'nodejs' };
