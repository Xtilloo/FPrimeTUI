# Future Changes

1. **Hide Intermediary Steps**: Currently, the TUI prints all intermediate tool requests and results (like `read_file` raw outputs) to the chat log. While good for debugging, this clutters the UI. In the future, these should be hidden from the user, perhaps relegated to an expanding "Agent Thought Process" toggle, so the user only sees conversational text.
2. **Dynamic UI Scrolling Freeze**: Scrolling up or down while the AI is generating tokens causes the UI to freeze/stutter. This likely indicates an issue with `scroll_end(animate=False)` being spammed on every token chunk, fighting the user's manual scroll events. This needs to be optimized in the next phase.
3. **Multi-line Input Field**: The main input field currently forces all text onto a single horizontal line, requiring scrolling for long prompts. This should be refactored into a `TextArea` or dynamically expanding `Input` so users can comfortably read long instructions.
4. **Animated "Thinking" State**: The static `*Thinking...*` text should be replaced with an animated ellipsis or spinner (using Textual's `LoadingIndicator` or an interval timer) to provide better visual feedback while waiting for the LLM's first token.
5. **Command Output Summarization**: When commands like `/build` complete, the tool shouldn't just dump the raw output and exit code. Instead, the AI should provide a brief, conversational summary: e.g., "Build succeeded. You're all good!" or "Build failed because of X."
6. **JPL F' Theming & Color Palette**: The default Textual color scheme (teal code blocks, green prompts, pine accents) needs to be replaced with a strict JPL/F' theme. Colors should reflect Mars, space, and NASA (e.g., deep space dark greys, rusty Mars reds/oranges, NASA blue/white).
7. **UI Polish & Styling**: 
    - Smooth out the prompt input bar at the bottom (remove the weird border lines on the left and right).
    - Fix the appearance of the scrollbar to make it less intrusive and cleaner.
    - Change the main application background color from harsh black to a softer dark grey.

    8. **Enhanced Flight Plan Visualization**: Currently, Flight Plans are rendered as standard Markdown headers with an emoji. In the future, this should be a specialized UI widget (e.g., a side-panel checklist or a collapsible tree) that updates in real-time as the agent completes each step.