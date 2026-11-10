/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { cleanup, render, screen } from "@testing-library/react";
import { ProviderCard } from "./ProviderCard";
import type { ProviderInfo, ProviderTestResult } from "../../types/api";

function llmProvider(overrides: Partial<ProviderInfo> = {}): ProviderInfo {
  return {
    id: "groq",
    name: "Groq",
    kind: "llm",
    description: "Fast LPU inference for OpenAI-compatible chat models.",
    env_var: "GROQ_API_KEY",
    configured: false,
    selected: false,
    capabilities: ["diagnosis"],
    model: "openai/gpt-oss-120b",
    default_model: "openai/gpt-oss-120b",
    connection_test_supported: true,
    ...overrides,
  };
}

const gnaniProvider: ProviderInfo = {
  id: "gnani",
  name: "Gnani",
  kind: "speech",
  description: "Gnani speech services.",
  env_var: "GNANI_API",
  configured: true,
  selected: null,
  capabilities: ["stt", "tts"],
  model: null,
  default_model: null,
  connection_test_supported: false,
};

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("ProviderCard", () => {
  it("renders provider metadata with configured and active badges", () => {
    render(
      <ProviderCard
        provider={llmProvider({ configured: true, selected: true })}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
      />,
    );
    expect(screen.getByText("Groq")).toBeDefined();
    expect(screen.getByText("Configured")).toBeDefined();
    expect(screen.getByText("Active provider")).toBeDefined();
    expect(
      screen.getByText("Fast LPU inference for OpenAI-compatible chat models."),
    ).toBeDefined();
  });

  it("shows an unconfigured badge when no key is stored", () => {
    render(
      <ProviderCard provider={llmProvider()} onSaveKey={vi.fn()} onRemoveKey={vi.fn()} />,
    );
    expect(screen.getByText("Not configured")).toBeDefined();
    expect(screen.queryByText("Remove")).toBeNull();
  });

  it("masks the API key and reveals it only on demand", async () => {
    const user = userEvent.setup();
    render(
      <ProviderCard provider={llmProvider()} onSaveKey={vi.fn()} onRemoveKey={vi.fn()} />,
    );
    const input = screen.getByLabelText("API key") as HTMLInputElement;
    await user.type(input, "gsk-secret-value");
    expect(input.type).toBe("password");

    await user.click(screen.getByRole("button", { name: "Show API key" }));
    expect(input.type).toBe("text");

    await user.click(screen.getByRole("button", { name: "Hide API key" }));
    expect(input.type).toBe("password");
  });

  it("saves a trimmed key, clears the field and never persists the value", async () => {
    const user = userEvent.setup();
    const onSaveKey = vi.fn().mockResolvedValue(true);
    render(
      <ProviderCard provider={llmProvider()} onSaveKey={onSaveKey} onRemoveKey={vi.fn()} />,
    );
    const input = screen.getByLabelText("API key") as HTMLInputElement;
    await user.type(input, "  gsk-secret-value  ");
    await user.click(screen.getByRole("button", { name: "Save key" }));

    expect(onSaveKey).toHaveBeenCalledWith("gsk-secret-value");
    expect(screen.getByTestId("provider-notice").textContent).toBe(
      "API key configured ✓",
    );
    // The secret never remains in the DOM after a successful save.
    expect(input.value).toBe("");
    expect(screen.queryByText(/gsk-secret-value/)).toBeNull();
    // And it is never written to browser storage.
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("keeps the typed key when saving fails", async () => {
    const user = userEvent.setup();
    const onSaveKey = vi.fn().mockRejectedValue(new Error("Bridge rejected the key."));
    render(
      <ProviderCard provider={llmProvider()} onSaveKey={onSaveKey} onRemoveKey={vi.fn()} />,
    );
    await user.type(screen.getByLabelText("API key"), "gsk-secret-value");
    await user.click(screen.getByRole("button", { name: "Save key" }));

    expect(screen.getByTestId("provider-notice").textContent).toBe(
      "Bridge rejected the key.",
    );
    expect((screen.getByLabelText("API key") as HTMLInputElement).value).toBe(
      "gsk-secret-value",
    );
  });

  it("disables saving while the key field is empty", () => {
    render(
      <ProviderCard provider={llmProvider()} onSaveKey={vi.fn()} onRemoveKey={vi.fn()} />,
    );
    expect(
      (screen.getByRole("button", { name: "Save key" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("removes a configured key on request", async () => {
    const user = userEvent.setup();
    const onRemoveKey = vi.fn().mockResolvedValue(true);
    render(
      <ProviderCard
        provider={llmProvider({ configured: true })}
        onSaveKey={vi.fn()}
        onRemoveKey={onRemoveKey}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(onRemoveKey).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("provider-notice").textContent).toBe("API key removed.");
  });

  it("does not allow selecting an LLM provider before its key is configured", () => {
    render(
      <ProviderCard
        provider={llmProvider({ configured: false })}
        onSelectProvider={vi.fn()}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
      />,
    );
    expect(
      (screen.getByRole("button", { name: "Use this provider" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
    expect(screen.getByText(/Save an API key before selecting/i)).toBeDefined();
  });

  it("switches the active provider through the selection button", async () => {
    const user = userEvent.setup();
    const onSelectProvider = vi.fn();
    const { rerender } = render(
      <ProviderCard
        provider={llmProvider({ configured: true })}
        onSelectProvider={onSelectProvider}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Use this provider" }));
    expect(onSelectProvider).toHaveBeenCalledTimes(1);

    rerender(
      <ProviderCard
        provider={llmProvider({ selected: true })}
        onSelectProvider={onSelectProvider}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
      />,
    );
    const selected = screen.getByRole("button", { name: "Selected" });
    expect(selected).toBeDefined();
    expect((selected as HTMLButtonElement).disabled).toBe(true);
  });

  it("tracks model edits and saves trimmed model ids", async () => {
    const user = userEvent.setup();
    const onSaveModel = vi.fn().mockResolvedValue(true);
    render(
      <ProviderCard
        provider={llmProvider()}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
        onSaveModel={onSaveModel}
      />,
    );
    const saveModel = screen.getByRole("button", {
      name: "Save model",
    }) as HTMLButtonElement;
    expect(saveModel.disabled).toBe(true);

    const modelInput = screen.getByLabelText(/Model ID/);
    await user.clear(modelInput);
    await user.type(modelInput, "  llama-3.1-8b-instant  ");
    expect(saveModel.disabled).toBe(false);
    await user.click(saveModel);

    expect(onSaveModel).toHaveBeenCalledWith("llama-3.1-8b-instant");
    expect(screen.getByTestId("provider-notice").textContent).toBe("Model saved.");
  });

  it("renders success, warning and failure connection test results", async () => {
    const user = userEvent.setup();
    const results: ProviderTestResult[] = [
      {
        provider: "groq",
        ok: true,
        message: "Groq accepted the API key and model 'openai/gpt-oss-120b' is listed in the model catalog. This check does not verify inference access.",
        model: "openai/gpt-oss-120b",
        model_ok: true,
      },
      {
        provider: "groq",
        ok: true,
        message: "Groq accepted the API key, but model 'missing' is not in its current model catalog. Check the model ID.",
        model: "missing",
        model_ok: false,
      },
      {
        provider: "groq",
        ok: true,
        message: "Groq accepted the API key, but its model catalog did not confirm whether 'openai/gpt-oss-120b' is available. This check does not run inference.",
        model: "openai/gpt-oss-120b",
        model_ok: null,
      },
      {
        provider: "groq",
        ok: false,
        message: "Groq rejected the API key (HTTP 401). Check the saved key.",
        model: "m",
        model_ok: null,
      },
    ];
    const onTestConnection = vi
      .fn()
      .mockImplementationOnce(async () => results[0])
      .mockImplementationOnce(async () => results[1])
      .mockImplementationOnce(async () => results[2])
      .mockImplementationOnce(async () => results[3]);
    const { rerender } = render(
      <ProviderCard
        provider={llmProvider({ configured: true })}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
        onTestConnection={onTestConnection}
      />,
    );
    for (const expected of results) {
      await user.click(screen.getByRole("button", { name: "Test connection" }));
      expect(screen.getByTestId("provider-test-result").textContent).toContain(
        expected.message,
      );
      rerender(
        <ProviderCard
          provider={llmProvider({ configured: true })}
          onSaveKey={vi.fn()}
          onRemoveKey={vi.fn()}
          onTestConnection={onTestConnection}
        />,
      );
    }
  });

  it("disables connection testing until a key is configured", () => {
    render(
      <ProviderCard
        provider={llmProvider({ configured: false })}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
        onTestConnection={vi.fn()}
      />,
    );
    expect(
      (screen.getByRole("button", { name: "Test connection" }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it("renders connection test errors as failures", async () => {
    const user = userEvent.setup();
    const onTestConnection = vi.fn().mockRejectedValue(new Error("Network down."));
    render(
      <ProviderCard
        provider={llmProvider({ configured: true })}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
        onTestConnection={onTestConnection}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Test connection" }));
    expect(screen.getByTestId("provider-test-result").textContent).toContain(
      "Network down.",
    );
  });

  it("disables every action while a global operation is busy", () => {
    render(
      <ProviderCard
        provider={llmProvider({ configured: true })}
        busy
        onSelectProvider={vi.fn()}
        onSaveKey={vi.fn()}
        onRemoveKey={vi.fn()}
        onSaveModel={vi.fn()}
        onTestConnection={vi.fn()}
      />,
    );
    for (const name of [
      "Use this provider",
      "Save key",
      "Remove",
      "Save model",
      "Test connection",
    ]) {
      expect(
        (screen.getByRole("button", { name }) as HTMLButtonElement).disabled,
      ).toBe(true);
    }
  });

  it("renders the Gnani speech card without model or connection sections", () => {
    render(
      <ProviderCard provider={gnaniProvider} onSaveKey={vi.fn()} onRemoveKey={vi.fn()} />,
    );
    expect(screen.getByText(/STT · Prisma enabled/)).toBeDefined();
    expect(screen.getByText(/TTS · Timbre enabled/)).toBeDefined();
    expect(screen.queryByLabelText("Model ID")).toBeNull();
    expect(screen.queryByRole("button", { name: "Test connection" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Use this provider" })).toBeNull();
  });

  it("explains that Gnani has no credential-only verification", () => {
    render(
      <ProviderCard provider={gnaniProvider} onSaveKey={vi.fn()} onRemoveKey={vi.fn()} />,
    );
    expect(screen.getByText(/speech pipeline itself verifies/i)).toBeDefined();
  });
});
