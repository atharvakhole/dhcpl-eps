"""
Modbus RS485 Stress Test
Tests concurrent read operations across multiple slaves through TCP gateway
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
import statistics

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException


@dataclass
class ReadResult:
    """Single read operation result"""
    slave_id: int
    client_id: int
    iteration: int
    registers: List[int]
    success: bool
    duration_ms: float
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ClientMetrics:
    """Metrics for a single client"""
    client_id: int
    slave_id: int
    total_reads: int
    successful_reads: int
    failed_reads: int
    total_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    avg_duration_ms: float
    median_duration_ms: float
    requests_per_second: float


@dataclass
class SlaveMetrics:
    """Aggregated metrics for all clients of one slave"""
    slave_id: int
    total_clients: int
    total_reads: int
    successful_reads: int
    failed_reads: int
    success_rate: float
    avg_duration_ms: float
    median_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    total_duration_seconds: float
    requests_per_second: float


@dataclass
class OverallMetrics:
    """System-wide metrics"""
    total_slaves: int
    total_clients: int
    total_reads: int
    successful_reads: int
    failed_reads: int
    overall_success_rate: float
    total_duration_seconds: float
    overall_requests_per_second: float
    avg_duration_ms: float
    median_duration_ms: float
    slowest_slave: int
    fastest_slave: int


class ModbusStressTester:
    """Stress test Modbus TCP gateway with multiple concurrent clients"""
    
    def __init__(
        self,
        host: str,
        port: int,
        slave_ids: List[int],
        registers: List[int],
        clients_per_slave: int,
        iterations_per_client: int,
        timeout: float = 5.0
    ):
        self.host = host
        self.port = port
        self.slave_ids = slave_ids
        self.registers = registers
        self.clients_per_slave = clients_per_slave
        self.iterations_per_client = iterations_per_client
        self.timeout = timeout
        
        self.results: List[ReadResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
    async def create_client(self) -> AsyncModbusTcpClient:
        """Create a new Modbus TCP client"""
        client = AsyncModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout
        )
        await client.connect()
        return client
    
    async def read_registers_for_slave(
        self,
        client: AsyncModbusTcpClient,
        slave_id: int,
        client_id: int,
        iteration: int
    ) -> ReadResult:
        """Read registers from a specific slave"""
        start = time.time()
        
        try:
            # Read holding registers
            response = await client.read_holding_registers(
                address=min(self.registers),
                count=max(self.registers) - min(self.registers) + 1,
                slave=slave_id
            )
            
            duration_ms = (time.time() - start) * 1000
            
            if response.isError():
                return ReadResult(
                    slave_id=slave_id,
                    client_id=client_id,
                    iteration=iteration,
                    registers=[],
                    success=False,
                    duration_ms=duration_ms,
                    error=str(response)
                )
            
            # Extract only the registers we care about
            values = []
            for reg in self.registers:
                idx = reg - min(self.registers)
                if idx < len(response.registers):
                    values.append(response.registers[idx])
            
            return ReadResult(
                slave_id=slave_id,
                client_id=client_id,
                iteration=iteration,
                registers=values,
                success=True,
                duration_ms=duration_ms
            )
            
        except ModbusException as e:
            duration_ms = (time.time() - start) * 1000
            return ReadResult(
                slave_id=slave_id,
                client_id=client_id,
                iteration=iteration,
                registers=[],
                success=False,
                duration_ms=duration_ms,
                error=f"ModbusException: {str(e)}"
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return ReadResult(
                slave_id=slave_id,
                client_id=client_id,
                iteration=iteration,
                registers=[],
                success=False,
                duration_ms=duration_ms,
                error=f"Exception: {str(e)}"
            )
    
    async def run_client(self, slave_id: int, client_id: int) -> List[ReadResult]:
        """Run iterations for a single client"""
        client = await self.create_client()
        results = []
        
        try:
            for iteration in range(self.iterations_per_client):
                result = await self.read_registers_for_slave(
                    client, slave_id, client_id, iteration
                )
                results.append(result)
                self.results.append(result)
                
                # Small delay to prevent overwhelming (optional, comment out for max stress)
                # await asyncio.sleep(0.01)
                
        finally:
            client.close()
        
        return results
    
    async def run_all_clients(self):
        """Run all clients concurrently"""
        tasks = []
        
        # Create tasks for all clients across all slaves
        for slave_id in self.slave_ids:
            for client_id in range(self.clients_per_slave):
                task = self.run_client(slave_id, client_id)
                tasks.append(task)
        
        print(f"\n{'='*80}")
        print(f"Starting stress test:")
        print(f"  Slaves: {len(self.slave_ids)} (IDs: {self.slave_ids})")
        print(f"  Clients per slave: {self.clients_per_slave}")
        print(f"  Iterations per client: {self.iterations_per_client}")
        print(f"  Total concurrent operations: {len(tasks) * self.iterations_per_client}")
        print(f"  Registers to read: {self.registers}")
        print(f"  Target: {self.host}:{self.port}")
        print(f"{'='*80}\n")
        
        self.start_time = time.time()
        
        # Run all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.end_time = time.time()
    
    def calculate_client_metrics(self) -> Dict[tuple, ClientMetrics]:
        """Calculate metrics for each client"""
        client_results = defaultdict(list)
        
        # Group results by (slave_id, client_id)
        for result in self.results:
            key = (result.slave_id, result.client_id)
            client_results[key].append(result)
        
        metrics = {}
        for (slave_id, client_id), results in client_results.items():
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            durations = [r.duration_ms for r in successful]
            
            if durations:
                total_duration = sum(durations)
                metrics[(slave_id, client_id)] = ClientMetrics(
                    client_id=client_id,
                    slave_id=slave_id,
                    total_reads=len(results),
                    successful_reads=len(successful),
                    failed_reads=len(failed),
                    total_duration_ms=total_duration,
                    min_duration_ms=min(durations),
                    max_duration_ms=max(durations),
                    avg_duration_ms=statistics.mean(durations),
                    median_duration_ms=statistics.median(durations),
                    requests_per_second=len(successful) / (total_duration / 1000)
                )
            else:
                metrics[(slave_id, client_id)] = ClientMetrics(
                    client_id=client_id,
                    slave_id=slave_id,
                    total_reads=len(results),
                    successful_reads=0,
                    failed_reads=len(failed),
                    total_duration_ms=0,
                    min_duration_ms=0,
                    max_duration_ms=0,
                    avg_duration_ms=0,
                    median_duration_ms=0,
                    requests_per_second=0
                )
        
        return metrics
    
    def calculate_slave_metrics(self, client_metrics: Dict[tuple, ClientMetrics]) -> Dict[int, SlaveMetrics]:
        """Calculate aggregated metrics per slave"""
        slave_results = defaultdict(list)
        
        # Group results by slave_id
        for result in self.results:
            slave_results[result.slave_id].append(result)
        
        metrics = {}
        for slave_id, results in slave_results.items():
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            durations = [r.duration_ms for r in successful]
            
            if durations:
                metrics[slave_id] = SlaveMetrics(
                    slave_id=slave_id,
                    total_clients=self.clients_per_slave,
                    total_reads=len(results),
                    successful_reads=len(successful),
                    failed_reads=len(failed),
                    success_rate=len(successful) / len(results) * 100,
                    avg_duration_ms=statistics.mean(durations),
                    median_duration_ms=statistics.median(durations),
                    min_duration_ms=min(durations),
                    max_duration_ms=max(durations),
                    total_duration_seconds=sum(durations) / 1000,
                    requests_per_second=len(successful) / (sum(durations) / 1000)
                )
            else:
                metrics[slave_id] = SlaveMetrics(
                    slave_id=slave_id,
                    total_clients=self.clients_per_slave,
                    total_reads=len(results),
                    successful_reads=0,
                    failed_reads=len(failed),
                    success_rate=0,
                    avg_duration_ms=0,
                    median_duration_ms=0,
                    min_duration_ms=0,
                    max_duration_ms=0,
                    total_duration_seconds=0,
                    requests_per_second=0
                )
        
        return metrics
    
    def calculate_overall_metrics(self, slave_metrics: Dict[int, SlaveMetrics]) -> OverallMetrics:
        """Calculate overall system metrics"""
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        durations = [r.duration_ms for r in successful]
        
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        slowest_slave = max(slave_metrics.items(), key=lambda x: x[1].avg_duration_ms)[0] if slave_metrics else 0
        fastest_slave = min(slave_metrics.items(), key=lambda x: x[1].avg_duration_ms)[0] if slave_metrics else 0
        
        return OverallMetrics(
            total_slaves=len(self.slave_ids),
            total_clients=len(self.slave_ids) * self.clients_per_slave,
            total_reads=len(self.results),
            successful_reads=len(successful),
            failed_reads=len(failed),
            overall_success_rate=len(successful) / len(self.results) * 100 if self.results else 0,
            total_duration_seconds=total_duration,
            overall_requests_per_second=len(successful) / total_duration if total_duration > 0 else 0,
            avg_duration_ms=statistics.mean(durations) if durations else 0,
            median_duration_ms=statistics.median(durations) if durations else 0,
            slowest_slave=slowest_slave,
            fastest_slave=fastest_slave
        )
    
    def print_results(self):
        """Print comprehensive test results"""
        client_metrics = self.calculate_client_metrics()
        slave_metrics = self.calculate_slave_metrics(client_metrics)
        overall_metrics = self.calculate_overall_metrics(slave_metrics)
        
        print("\n" + "="*80)
        print("OVERALL METRICS")
        print("="*80)
        print(f"Total Test Duration:        {overall_metrics.total_duration_seconds:.2f} seconds")
        print(f"Total Slaves:               {overall_metrics.total_slaves}")
        print(f"Total Clients:              {overall_metrics.total_clients}")
        print(f"Total Read Operations:      {overall_metrics.total_reads}")
        print(f"Successful Reads:           {overall_metrics.successful_reads}")
        print(f"Failed Reads:               {overall_metrics.failed_reads}")
        print(f"Overall Success Rate:       {overall_metrics.overall_success_rate:.2f}%")
        print(f"Overall Throughput:         {overall_metrics.overall_requests_per_second:.2f} req/s")
        print(f"Average Response Time:      {overall_metrics.avg_duration_ms:.2f} ms")
        print(f"Median Response Time:       {overall_metrics.median_duration_ms:.2f} ms")
        print(f"Slowest Slave:              Slave {overall_metrics.slowest_slave}")
        print(f"Fastest Slave:              Slave {overall_metrics.fastest_slave}")
        
        print("\n" + "="*80)
        print("PER-SLAVE METRICS")
        print("="*80)
        for slave_id in sorted(slave_metrics.keys()):
            metrics = slave_metrics[slave_id]
            print(f"\nSlave {slave_id}:")
            print(f"  Total Reads:              {metrics.total_reads}")
            print(f"  Successful:               {metrics.successful_reads}")
            print(f"  Failed:                   {metrics.failed_reads}")
            print(f"  Success Rate:             {metrics.success_rate:.2f}%")
            print(f"  Avg Response Time:        {metrics.avg_duration_ms:.2f} ms")
            print(f"  Median Response Time:     {metrics.median_duration_ms:.2f} ms")
            print(f"  Min Response Time:        {metrics.min_duration_ms:.2f} ms")
            print(f"  Max Response Time:        {metrics.max_duration_ms:.2f} ms")
            print(f"  Throughput:               {metrics.requests_per_second:.2f} req/s")
        
        print("\n" + "="*80)
        print("PER-CLIENT METRICS")
        print("="*80)
        for slave_id in sorted(self.slave_ids):
            print(f"\nSlave {slave_id} Clients:")
            slave_clients = {k: v for k, v in client_metrics.items() if k[0] == slave_id}
            
            for (_, client_id), metrics in sorted(slave_clients.items()):
                print(f"  Client {client_id}:")
                print(f"    Total Reads:            {metrics.total_reads}")
                print(f"    Successful:             {metrics.successful_reads}")
                print(f"    Failed:                 {metrics.failed_reads}")
                print(f"    Avg Response:           {metrics.avg_duration_ms:.2f} ms")
                print(f"    Min/Max:                {metrics.min_duration_ms:.2f} / {metrics.max_duration_ms:.2f} ms")
        
        # Error summary
        failed_results = [r for r in self.results if not r.success]
        if failed_results:
            print("\n" + "="*80)
            print("ERROR SUMMARY")
            print("="*80)
            error_counts = defaultdict(int)
            for result in failed_results:
                error_counts[result.error] += 1
            
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {count}x: {error}")
        
        print("\n" + "="*80)


async def main():
    """Run the stress test"""
    
    # CONFIGURATION
    HOST = "192.168.1.100"  # Your Modbus TCP gateway IP
    PORT = 501  # Your Modbus TCP gateway port
    SLAVE_IDS = [1, 2, 3, 4, 5, 6]  # Your 6 slave devices
    REGISTERS = [100, 101, 102, 104, 105, 107, 109, 111]  # Registers to read
    CLIENTS_PER_SLAVE = 1  # Number of concurrent clients per slave
    ITERATIONS_PER_CLIENT = 100  # How many times each client reads
    TIMEOUT = 2.0  # Timeout for each read operation (seconds)
    
    # Create and run tester
    tester = ModbusStressTester(
        host=HOST,
        port=PORT,
        slave_ids=SLAVE_IDS,
        registers=REGISTERS,
        clients_per_slave=CLIENTS_PER_SLAVE,
        iterations_per_client=ITERATIONS_PER_CLIENT,
        timeout=TIMEOUT
    )
    
    await tester.run_all_clients()
    tester.print_results()


if __name__ == "__main__":
    asyncio.run(main())
