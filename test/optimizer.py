import torch, time
from torch import nn
import pypose as pp
from torch.autograd.functional import jacobian


class Timer:
    def __init__(self):
        torch.cuda.synchronize()
        self.start_time = time.time()

    def tic(self):
        self.start()

    def show(self, prefix="", output=True):
        torch.cuda.synchronize()
        duration = time.time()-self.start_time
        if output:
            print(prefix+"%fs" % duration)
        return duration

    def toc(self, prefix=""):
        self.end()
        print(prefix+"%fs = %fHz" % (self.duration, 1/self.duration))
        return self.duration

    def start(self):
        torch.cuda.synchronize()
        self.start_time = time.time()

    def end(self, reset=True):
        torch.cuda.synchronize()
        self.duration = time.time()-self.start_time
        if reset:
            self.start_time = time.time()
        return self.duration


import argparse
from torch import nn
import torch.utils.data as Data
from torchvision.datasets import MNIST
from torchvision import transforms as T
parser = argparse.ArgumentParser()
parser.add_argument('--device', default='cuda:0', type=str, help='device')
parser.add_argument('--epoch', default=20, type=int, help='epoch')
parser.add_argument('--batch-size', default=1000, type=int, help='epoch')
parser.add_argument('--damping', default=1e-6, type=float, help='Damping factor')
parser.add_argument('--gamma', default=2, type=float, help='Gamma')
args = parser.parse_args()


class Pose(nn.Module):
    def __init__(self, *dim):
        super().__init__()
        self.pose = pp.Parameter(pp.randn_se3(*dim))
        self.identity = pp.identity_se3(2, 2)

    def forward(self, inputs):
        e = (self.pose.Exp() @ inputs).Log()
        return (e - self.identity).abs().sum()

posnet = Pose(2, 2)
inputs = pp.randn_SE3(2, 2)
optimizer = torch.optim.SGD(posnet.parameters(), lr=1e-1)
scheduler = torch.optim.lr_scheduler.MultiStepLR(optimizer, [50, 70], gamma=0.1)
timer = Timer()

for idx in range(100):
    optimizer.zero_grad()
    scheduler.step()
    loss = posnet(inputs)
    loss.backward()
    optimizer.step()
    print('Pose loss %.7f @ %dit, Timing: %.3fs'%(loss.sum(), idx, timer.end()))
    if loss.sum() < 1e-7:
        print('Early Stoping!')
        print('Optimization Early Done with loss:', loss.sum().item())
        break
print('Done', timer.toc())



class PoseInv(nn.Module):
    def __init__(self, *dim):
        super().__init__()
        self.pose = pp.Parameter(pp.randn_se3(*dim))

    def forward(self, inputs):
        return (self.pose.Exp() @ inputs).Log().abs()

posnet = PoseInv(2, 2)
inputs = pp.randn_SE3(2, 2)
optimizer = pp.optim.LM(posnet, dampening=args.damping)
timer = Timer()

for idx in range(10):
    loss = optimizer.step(inputs)
    loss = sum([l.sum() for l in loss])
    print('Pose loss %.7f @ %dit, Timing: %.3fs'%(loss, idx, timer.end()))
    if loss < 1e-5:
        print('Early Stoping!')
        print('Optimization Early Done with loss:', loss.sum().item())
        break
