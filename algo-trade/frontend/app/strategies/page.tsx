import { BarChart2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export default function StrategiesPage() {
  return (
    <div className="p-5 md:p-6">
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 gap-3 text-center">
          <BarChart2 className="w-8 h-8 text-zinc-600" />
          <p className="text-sm font-medium text-zinc-400">Strategies</p>
          <p className="text-xs text-zinc-600 max-w-xs">
            Configure and monitor your algorithmic trading strategies here.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
