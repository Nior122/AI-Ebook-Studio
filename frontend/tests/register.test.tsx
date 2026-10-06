import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import SignUpPage from "@/app/sign-up/[[...sign-up]]/page";
import { renderWithProviders } from "./test-utils";

describe("SignUpPage", () => {
  it("renders the Clerk sign-up widget on the current sign-up route", () => {
    renderWithProviders(<SignUpPage />);

    expect(screen.getByText("Clerk sign-up widget")).toBeInTheDocument();
  });
});
