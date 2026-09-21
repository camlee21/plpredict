import { QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { apiRequest } from "../api/client";
import { createQueryClient } from "../api/queries";
import { AuthProvider, useAuth } from "./AuthContext";

jest.mock("../api/client", () => ({
  apiRequest: jest.fn(),
  clearTokens: jest.fn(),
  setTokens: jest.fn(),
}));

const SAVED = { id: 7, username: "saved-name" };

function Probe() {
  const { user, loading, logout } = useAuth();
  return (
    <>
      <span data-testid="state">{loading ? "loading" : user ? user.username : "logged out"}</span>
      <button onClick={logout}>log out</button>
    </>
  );
}

function renderAuth(client = createQueryClient()) {
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>
  );
  return client;
}

const state = () => screen.getByTestId("state").textContent;
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

beforeEach(() => {
  localStorage.clear();
  apiRequest.mockReset();
});

describe("AuthProvider", () => {
  test("with a saved profile, the app renders at once, then takes the server's answer", async () => {
    localStorage.setItem("access", "token");
    localStorage.setItem("user", JSON.stringify(SAVED));
    const me = deferred();
    apiRequest.mockReturnValue(me.promise);

    renderAuth();
    // No waiting on the server before showing anything.
    expect(state()).toBe("saved-name");

    await act(async () => me.resolve({ ...SAVED, username: "renamed" }));
    expect(state()).toBe("renamed");
    expect(JSON.parse(localStorage.getItem("user")).username).toBe("renamed");
  });

  test("a slow or unreachable server doesn't log you out", async () => {
    localStorage.setItem("access", "token");
    localStorage.setItem("user", JSON.stringify(SAVED));
    apiRequest.mockRejectedValue(new TypeError("Failed to fetch"));

    renderAuth();
    await waitFor(() => expect(apiRequest).toHaveBeenCalled());
    await act(async () => {});
    expect(state()).toBe("saved-name");
  });

  test("an expired session logs you out and wipes the cached data", async () => {
    localStorage.setItem("access", "token");
    localStorage.setItem("user", JSON.stringify(SAVED));
    localStorage.setItem("plpredict-cache", "{}");
    apiRequest.mockRejectedValue(Object.assign(new Error("Unauthorized"), { status: 401 }));
    const client = createQueryClient();
    client.setQueryData(["predictions", "history"], { overall_total: 5 });

    renderAuth(client);
    await waitFor(() => expect(state()).toBe("logged out"));
    expect(client.getQueryData(["predictions", "history"])).toBeUndefined();
    expect(localStorage.getItem("plpredict-cache")).toBeNull();
    expect(localStorage.getItem("user")).toBeNull();
  });

  test("without a saved profile it waits for the server, as before", async () => {
    localStorage.setItem("access", "token");
    const me = deferred();
    apiRequest.mockReturnValue(me.promise);

    renderAuth();
    expect(state()).toBe("loading");
    await act(async () => me.resolve(SAVED));
    expect(state()).toBe("saved-name");
  });

  test("logging out wipes the cache in memory and the saved copy", async () => {
    localStorage.setItem("access", "token");
    localStorage.setItem("user", JSON.stringify(SAVED));
    localStorage.setItem("plpredict-cache", "{}");
    apiRequest.mockResolvedValue(SAVED);
    const client = createQueryClient();
    client.setQueryData(["leagues", "mine"], [{ public_id: "AAA" }]);

    renderAuth(client);
    await act(async () => {});
    await act(async () => screen.getByText("log out").click());

    expect(state()).toBe("logged out");
    expect(client.getQueryData(["leagues", "mine"])).toBeUndefined();
    expect(localStorage.getItem("plpredict-cache")).toBeNull();
    expect(localStorage.getItem("user")).toBeNull();
  });
});
