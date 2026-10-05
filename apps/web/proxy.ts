import { NextResponse, type NextRequest } from "next/server";

import { CURRENCY_COOKIE, DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from "@/i18n/config";

const YEAR = 60 * 60 * 24 * 365;

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

  // English by default. The cookie is only set when the visitor picks a language from the header dropdown;
  // a shared link in another language still opens in that language.
  const cookieLocale = req.cookies.get(LOCALE_COOKIE)?.value;
  const first = pathname.split("/")[1];
  if (!isLocale(first)) {
    const target = isLocale(cookieLocale) ? cookieLocale : DEFAULT_LOCALE;
    const rest = pathname === "/" ? "" : pathname;
    return NextResponse.redirect(new URL(`/${target}${rest}${search}`, req.url));
  }
  const res = NextResponse.next();

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

