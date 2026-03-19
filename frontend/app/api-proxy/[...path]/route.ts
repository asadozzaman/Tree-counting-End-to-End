import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function targetBaseUrl(): string {
  return process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
}

async function forward(request: NextRequest, pathParts: string[]) {
  const url = `${targetBaseUrl()}/${pathParts.join("/")}${request.nextUrl.search}`;

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  const method = request.method;
  const init: RequestInit = { method, headers, redirect: "manual", cache: "no-store" };

  if (method !== "GET" && method !== "HEAD") {
    const buffer = await request.arrayBuffer();
    init.body = buffer.byteLength > 0 ? buffer : undefined;
  }

  const upstream = await fetch(url, init);
  const outputHeaders = new Headers(upstream.headers);
  outputHeaders.delete("transfer-encoding");
  outputHeaders.delete("content-encoding");

  return new Response(upstream.body, {
    status: upstream.status,
    headers: outputHeaders
  });
}

export async function GET(request: NextRequest, context: { params: { path: string[] } }) {
  return forward(request, context.params.path || []);
}

export async function POST(request: NextRequest, context: { params: { path: string[] } }) {
  return forward(request, context.params.path || []);
}

export async function DELETE(request: NextRequest, context: { params: { path: string[] } }) {
  return forward(request, context.params.path || []);
}