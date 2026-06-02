import React, { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error("[ErrorBoundary]", error, info);
  }

  reset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (!this.state.hasError || !this.state.error) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback(this.state.error, this.reset);
    }

    return (
      <div style={{ padding: "1rem" }}>
        <div
          style={{
            backgroundColor: "var(--color-error-bg, #fef2f2)",
            border: "1px solid var(--color-error-border, #fca5a5)",
            borderRadius: "0.5rem",
            padding: "1rem",
            color: "var(--color-error-text, #991b1b)",
          }}
        >
          <h3 style={{ margin: "0 0 0.5rem", fontSize: "1rem", fontWeight: 600 }}>
            Something went wrong
          </h3>
          <pre
            style={{
              fontFamily: "monospace",
              fontSize: "0.875rem",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              margin: "0 0 0.75rem",
            }}
          >
            {this.state.error.message}
          </pre>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: "0.375rem 0.75rem",
                fontSize: "0.875rem",
                border: "1px solid currentColor",
                borderRadius: "0.375rem",
                background: "transparent",
                color: "inherit",
                cursor: "pointer",
              }}
            >
              Reload page
            </button>
            <button
              onClick={this.reset}
              style={{
                padding: "0.375rem 0.75rem",
                fontSize: "0.875rem",
                border: "1px solid currentColor",
                borderRadius: "0.375rem",
                background: "transparent",
                color: "inherit",
                cursor: "pointer",
              }}
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ErrorBoundaryProps["fallback"],
): React.ComponentType<P> {
  const displayName = WrappedComponent.displayName || WrappedComponent.name || "Component";
  const HOC = (props: P) => (
    <ErrorBoundary fallback={fallback}>
      <WrappedComponent {...props} />
    </ErrorBoundary>
  );
  HOC.displayName = `withErrorBoundary(${displayName})`;
  return HOC;
}
