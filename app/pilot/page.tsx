import { notFound } from 'next/navigation';
import PilotClient from './PilotClient';

// Internal dev/QA page (demo dev-login accounts, internal emails). Hidden in
// production builds unless explicitly enabled for a preview environment
// (security review 1405-08-17). The backend dev-login stays disabled outside
// ENVIRONMENT=development regardless of this flag.
export default function PilotPage() {
  const enabled = process.env.NEXT_PUBLIC_ENABLE_PILOT === '1' || process.env.NODE_ENV === 'development';
  if (!enabled) notFound();
  return <PilotClient />;
}
