import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
    const isAuthPage = request.nextUrl.pathname.startsWith('/login') || request.nextUrl.pathname.startsWith('/register');
    const token = request.cookies.get('superactive_auth');

    // If trying to access dashboard pages without a token, redirect to login
    if (!token && !isAuthPage) {
        return NextResponse.redirect(new URL('/login', request.url));
    }

    // If trying to access auth pages WITH a token, redirect to dashboard
    if (token && isAuthPage) {
        return NextResponse.redirect(new URL('/', request.url));
    }

    return NextResponse.next();
}

// Config to decide which paths the middleware runs on.
// We want to protect all dashboard pages, but allow static files and api routes
export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - api (API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         */
        '/((?!api|_next/static|_next/image|favicon.ico).*)',
    ],
};
