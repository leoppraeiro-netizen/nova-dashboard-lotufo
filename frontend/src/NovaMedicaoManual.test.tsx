import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { NovaMedicaoManual } from "./Medicoes";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("./api", async (original) => ({ ...(await original<typeof import("./api")>()), api }));

afterEach(() => { cleanup(); api.mockReset(); });

it("nova medição manual: digitar 092026 manda a competência 2026-09", async () => {
  api.mockResolvedValueOnce({ id: 5 });
  render(<NovaMedicaoManual contratoId={3} aoCriar={() => {}} />);
  fireEvent.change(screen.getByLabelText("Nº"), { target: { value: "7" } });
  fireEvent.change(screen.getByLabelText("Competência"), { target: { value: "092026" } });
  fireEvent.click(screen.getByRole("button", { name: /Nova medição/ }));
  await waitFor(() => expect(api).toHaveBeenCalled());
  expect(api).toHaveBeenCalledWith("/api/contratos/3/medicoes", expect.objectContaining({
    method: "POST", body: JSON.stringify({ numero: 7, tipo: "execucao", competencia: "2026-09" }) }));
});
