import { Briefcase } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export default function PositionsPage() {
  return (
    <div className="p-5 md:p-6">
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 gap-3 text-center">
          <Briefcase className="w-8 h-8 text-zinc-600" />
          <p className="text-sm font-medium text-zinc-400">Positions</p>
          <p className="text-xs text-zinc-600 max-w-xs">
            Your open and closed positions will appear here.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
