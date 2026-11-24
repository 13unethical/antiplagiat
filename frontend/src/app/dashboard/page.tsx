"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getUser } from "@/lib/auth";

export default function DashboardRedirect() {
  const router = useRouter();
  useEffect(() => {
    const user = getUser();
    if (!user) { router.replace("/login"); return; }
    if (user.role === "teacher") router.replace("/checks/new");
    else if (user.role === "school_admin") router.replace("/admin");
    else router.replace("/super");
  }, [router]);
  return null;
}
