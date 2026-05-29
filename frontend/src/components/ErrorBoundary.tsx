import { Component, type ErrorInfo, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error boundary:", error, info);
    toast.error("Something went wrong", {
      description: error.message || "An unexpected error occurred.",
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 text-center">
          <h2 className="text-lg font-semibold">Something went wrong</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            The page hit an unexpected error. Try reloading or go back to the run list.
          </p>
          <Button
            onClick={() => {
              this.setState({ hasError: false });
              window.location.href = "/runs";
            }}
          >
            Back to runs
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
