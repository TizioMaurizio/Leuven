import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="h-screen w-screen flex items-center justify-center bg-[#1a1b2e] text-white p-8">
          <div className="max-w-xl space-y-4">
            <h1 className="text-xl font-bold text-red-400">Runtime Error</h1>
            <pre className="text-sm text-gray-300 whitespace-pre-wrap bg-[#252640] rounded-lg p-4 overflow-auto max-h-[60vh]">
              {this.state.error.message}
              {'\n\n'}
              {this.state.error.stack}
            </pre>
            <button
              onClick={() => this.setState({ error: null })}
              className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-500"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
