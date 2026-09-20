import { ItemsPanel } from "@/components/ItemsPanel";
import { StatusPanel } from "@/components/StatusPanel";

/**
 * Home page of the demo workload.
 *
 * The page itself is a server component; both panels are client components because they call the demo
 * API from the browser through the same-origin `/api/*` rewrite configured in `next.config.ts`.
 */
export default function HomePage() {
  return (
    <>
      <StatusPanel />
      <ItemsPanel />
    </>
  );
}
