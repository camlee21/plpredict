import { render, screen } from "@testing-library/react";
import App from "./App";

// Jest 27 (Create React App) can't read the package's "exports" map, and tests
// shouldn't be sending page views anyway.
jest.mock("@vercel/analytics/react", () => ({ Analytics: () => null }), { virtual: true });

test("redirects an unauthenticated visitor to the login page", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
});
