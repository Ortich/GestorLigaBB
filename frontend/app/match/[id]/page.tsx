"use client";

import { useParams } from "next/navigation";
import { MatchFlow } from "@/components/MatchFlow";

export default function MatchPage() {
  const params = useParams<{ id: string }>();
  return <MatchFlow matchId={params.id} />;
}
