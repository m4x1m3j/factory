export const FactoryHooks = async ({ $ }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash" || typeof output.args.command !== "string") {
        return;
      }

      const command = output.args.command.trim();
      if (command && !command.startsWith("rtk ")) {
        output.args.command = `rtk ${command}`;
      }
    },
    "tool.execute.after": async (input) => {
      if (!["bash", "edit", "write"].includes(input.tool)) {
        return;
      }

      await $`uv run ruff check --fix . && uv run ruff format .`;
    },
  };
};