import { NextResponse, type NextRequest } from "next/server";

import { CURRENCY_COOKIE, DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from "@/i18n/config";

const YEAR = 60 * 60 * 24 * 365;

function fromAcceptLanguage(header: string | null): string | null {
  if (!header) return null;
  for (const part of header.split(",")) {
    const code = part.split(";")[0].trim().slice(0, 2).toLowerCase();
    if (isLocale(code)) return code;
  }
  return null;
}

function basicAuthOk(req: NextRequest): boolean {
  const expected = process.env.STAGING_BASIC_AUTH; // "user:pass"
  if (!expected) return true;
  const header = req.headers.get("authorization") ?? "";
  return header === `Basic ${btoa(expected)}`;
}

export function proxy(req: NextRequest) {
  if (!basicAuthOk(req)) {
    return new NextResponse("Authentication required", {
      status: 401, headers: { "WWW-Authenticate": 'Basic realm="staging"', "X-Robots-Tag": "noindex" },
    });
  }
  const { pathname, search } = req.nextUrl;

  if (pathname.startsWith("/admin")) {
    if (pathname !== "/admin/login" && !req.cookies.get("pp_staff")) {
      return NextResponse.redirect(new URL("/admin/login", req.url));
    }
    return NextResponse.next();
  }

  const cookieLocale = req.cookies.get(LOCALE_COOKIE)?.value;
  const first = pathname.split("/")[1];
  let res: NextResponse;

  if (pathname === "/") {
    // Returning visitor: straight to their language. First visit: full-screen language picker.
    if (isLocale(cookieLocale)) return NextResponse.redirect(new URL(`/${cookieLocale}${search}`, req.url));
    res = NextResponse.next();
  } else if (!isLocale(first)) {
    const target = (isLocale(cookieLocale) && cookieLocale)
      || fromAcceptLanguage(req.headers.get("accept-language")) || DEFAULT_LOCALE;
    return NextResponse.redirect(new URL(`/${target}${pathname}${search}`, req.url));
  } else {
    res = NextResponse.next();
    if (!isLocale(cookieLocale)) {
      res.cookies.set(LOCALE_COOKIE, first, { maxAge: YEAR, path: "/", sameSite: "lax" });
    }
  }

  if (!req.cookies.get(CURRENCY_COOKIE)) {
    // Visitors outside India see USD by default (they can switch). Unknown country -> INR.
    const country = req.headers.get("cf-ipcountry") ?? req.headers.get("x-vercel-ip-country") ?? "IN";
    res.cookies.set(CURRENCY_COOKIE, country.toUpperCase() === "IN" ? "INR" : "USD",
      { maxAge: YEAR, path: "/", sameSite: "lax" });
  }
  return res;
}

export const config = {
  // Everything except API proxying, static assets and metadata files.
  matcher: ["/((?!api/|_next/|media/|images/|favicon|icon|apple-icon|manifest|sw\\.js|sitemap\\.xml|robots\\.txt|.*\\..*).*)"],
};

