import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, errorMessage, query } from "../services/api.js";

describe("errorMessage", () => {
  it("passes through string details", () => {
    expect(errorMessage({ detail: "transaction not found" }, 404)).toBe("transaction not found");
  });
  it("flattens FastAPI validation errors with field paths", () => {
    const body = { detail: [{ loc: ["body", "simulation", "eve_probability"], msg: "Input should be <= 1" }] };
    expect(errorMessage(body, 422)).toBe("simulation.eve_probability: Input should be <= 1");
  });
  it("falls back to the status code", () => {
    expect(errorMessage(null, 500)).toBe("Request failed (500)");
  });
});

describe("query", () => {
  it("drops empty values", () => {
    expect(query({ status: "", limit: 15, offset: 0, x: null })).toBe("?limit=15&offset=0");
    expect(query({})).toBe("");
  });
});

describe("request", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts JSON and returns the body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ ok: 1 }) });
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.createTransfer({ amount: "1.00" })).resolves.toEqual({ ok: 1 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/transfers");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ amount: "1.00" });
  });

  it("raises ApiError with the server's message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 422, json: () => Promise.resolve({ detail: "banks must differ" }),
    }));
    await expect(api.createTransfer({})).rejects.toMatchObject({ message: "banks must differ", status: 422 });
  });

  it("explains an unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
    const err = await api.health().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toMatch(/Cannot reach the backend/);
  });

  it("URL-encodes ids", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    vi.stubGlobal("fetch", fetchMock);
    await api.transfer("a/b");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/transfers/a%2Fb");
  });
});
