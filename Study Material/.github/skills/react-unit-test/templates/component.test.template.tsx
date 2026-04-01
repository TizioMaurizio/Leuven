import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ComponentName } from '../ComponentName';

describe('ComponentName', () => {
  it('renders primary content', () => {
    render(<ComponentName />);

    expect(screen.getByText(/expected text/i)).toBeInTheDocument();
  });

  it('handles user interaction', async () => {
    const user = userEvent.setup();
    render(<ComponentName />);

    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(screen.getByText(/success/i)).toBeInTheDocument();
  });
});
