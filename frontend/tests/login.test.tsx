import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import SignInPage from "@/app/sign-in/[[...sign-in]]/page";
import { renderWithProviders } from "./test-utils";

describe("SignInPage", () => {
  it("renders the Clerk sign-in widget on the current sign-in route", () => {
    renderWithProviders(<SignInPage />);

    expect(screen.getByText("Clerk sign-in widget")).toBeInTheDocument();
  });
});
